"""Hybrid retrieval engine — metadata-first, semantic-second.

The retrieval strategy is:
  1. **Metadata filtering** — filter by namespace, owner, tags in PostgreSQL.
  2. **Candidate selection** — return all matching rows (with embeddings).
  3. **Semantic reranking** — if more candidates than ``limit``, rerank
     by cosine similarity to the query embedding.
  4. **Walrus fetch** — fetch full content from Walrus for the top results.

Vector search is explicitly NOT the primary retrieval mechanism.
Metadata filtering happens before any semantic computation.
"""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING, Any

import numpy as np

if TYPE_CHECKING:
    import asyncpg

    from membrane.models import MemoryRecord
    from membrane.walrus_client import WalrusClient

logger = logging.getLogger(__name__)


class EmbeddingEngine:
    """Lazy-loading wrapper around a FastEmbed TextEmbedding model."""

    def __init__(self, model_name: str = "all-MiniLM-L6-v2") -> None:
        self._model_name = model_name
        self._model: Any | None = None

    def _load_model(self) -> Any:
        """Load the model on first use."""
        if self._model is None:
            from fastembed import TextEmbedding

            model_name = self._model_name
            if model_name == "all-MiniLM-L6-v2":
                model_name = "sentence-transformers/all-MiniLM-L6-v2"

            logger.info("Loading embedding model: %s", model_name)
            self._model = TextEmbedding(model_name)
            logger.info("Embedding model loaded.")
        return self._model

    def encode(self, text: str) -> np.ndarray:
        """Encode a text string into a dense vector.

        Returns:
            1-D numpy array of float32 values.
        """
        model = self._load_model()
        # embed() returns an iterable of numpy arrays
        embeddings = list(model.embed([text]))
        return embeddings[0].astype(np.float32)


def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    """Compute cosine similarity between two vectors."""
    dot = np.dot(a, b)
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return float(dot / (norm_a * norm_b))


def semantic_rerank(
    query_embedding: np.ndarray | list[float],
    candidates: list[MemoryRecord],
    limit: int = 10,
) -> list[tuple[MemoryRecord, float]]:
    """Rerank candidate memories by cosine similarity to the query.

    Only candidates with embeddings are scored.  Candidates without
    embeddings are placed at the end with a score of 0.0.

    Args:
        query_embedding: Dense vector for the query.
        candidates: Pre-filtered memory records from metadata search.
        limit: Maximum results to return.

    Returns:
        List of (MemoryRecord, score) tuples sorted descending by score.
    """
    query_vec = np.array(query_embedding, dtype=np.float32)

    scored: list[tuple[MemoryRecord, float]] = []
    unscored: list[tuple[MemoryRecord, float]] = []

    for mem in candidates:
        if mem.embedding is not None:
            mem_vec = np.array(mem.embedding, dtype=np.float32)
            score = cosine_similarity(query_vec, mem_vec)
            scored.append((mem, score))
        else:
            unscored.append((mem, 0.0))

    # Sort scored descending, then append unscored
    scored.sort(key=lambda x: x[1], reverse=True)
    combined = scored + unscored
    return combined[:limit]


class RetrievalEngine:
    """Hybrid retrieval: metadata filtering → optional semantic reranking.

    Flow::

        search_memory(query)
        → metadata filtering (namespace, owner, tags)
        → candidate selection
        → optional semantic reranking (if candidates > limit)
        → fetch Walrus blobs for top results
        → return results
    """

    def __init__(self, embedding_engine: EmbeddingEngine) -> None:
        self._embedding_engine = embedding_engine

    async def search(
        self,
        db: asyncpg.Connection,
        walrus: WalrusClient,
        query: str,
        namespace: str | None = None,
        owner: str | None = None,
        allowed_user: str | None = None,
        tags: list[str] | None = None,
        limit: int = 10,
        encryption_key: str = "",
    ) -> list[dict[str, Any]]:
        """Execute a hybrid search: metadata-first, semantic-second.

        1. Filter by namespace/owner/tags in PostgreSQL.
        2. If more candidates than ``limit``, rerank with embeddings.
        3. Fetch Walrus content for top results.
        4. Return enriched results.
        """
        from membrane.memory_manager import MemoryManager

        # Step 1: Metadata filtering
        candidates = await self._metadata_filter(
            db, namespace=namespace, owner=owner, allowed_user=allowed_user, tags=tags
        )

        if not candidates:
            return []

        # Step 2: Semantic reranking for top-K candidates
        try:
            query_embedding = self._embedding_engine.encode(query)
            top_k_ranked = semantic_rerank(query_embedding, candidates, limit=limit)
            top_k_candidates = [c for c, _ in top_k_ranked]
        except Exception:
            logger.warning("Embedding model unavailable — returning unranked results.", exc_info=True)
            top_k_candidates = candidates[:limit]

        # Step 3: Context Expansion via memory_relations (1-hop)
        top_k_ids = [c.memory_id for c in top_k_candidates]
        expanded_candidates_map = {c.memory_id: c for c in top_k_candidates}

        if top_k_ids:
            # Query neighbors
            placeholders1 = ",".join(f"${i+1}" for i in range(len(top_k_ids)))
            placeholders2 = ",".join(f"${i+1+len(top_k_ids)}" for i in range(len(top_k_ids)))
            neighbor_query = f"""
                SELECT DISTINCT target_id as neighbor_id FROM memory_relations WHERE source_id IN ({placeholders1})
                UNION
                SELECT DISTINCT source_id as neighbor_id FROM memory_relations WHERE target_id IN ({placeholders2})
            """
            neighbor_rows = await db.fetch(neighbor_query, *(top_k_ids * 2))
            neighbor_ids = [row["neighbor_id"] for row in neighbor_rows if row["neighbor_id"] not in expanded_candidates_map]

            if neighbor_ids:
                # Fetch neighbor records
                n_placeholders = ",".join(f"${i+1}" for i in range(len(neighbor_ids)))
                n_rows = await db.fetch(f"SELECT * FROM memories WHERE memory_id IN ({n_placeholders})", *neighbor_ids)
                
                from membrane.memory_manager import _bytes_to_embedding
                from membrane.models import MemoryRecord
                
                for row in n_rows:
                    raw_emb = row["embedding"]
                    embedding = _bytes_to_embedding(raw_emb) if raw_emb is not None else None
                    rec = MemoryRecord(
                        memory_id=row["memory_id"],
                        namespace=row["namespace"],
                        owner=row["owner"],
                        visibility=dict(row).get("visibility", "private"),
                        allowed_agents=dict(row).get("allowed_agents", "[]"),
                        allowed_users=dict(row).get("allowed_users", "[]"),
                        tags=row["tags"],
                        timestamp=row["timestamp"],
                        walrus_blob_id=row["walrus_blob_id"],
                        content_hash=row["content_hash"],
                        proof_id=row["proof_id"],
                        embedding=embedding,
                    )
                    expanded_candidates_map[rec.memory_id] = rec

        expanded_candidates = list(expanded_candidates_map.values())

        # Step 4: Final semantic reranking on expanded set
        try:
            if 'query_embedding' not in locals():
                query_embedding = self._embedding_engine.encode(query)
            final_ranked = semantic_rerank(query_embedding, expanded_candidates, limit=limit)
        except Exception:
            final_ranked = [(c, 0.0) for c in expanded_candidates[:limit]]

        # Step 5: Fetch Walrus content for top results
        results: list[dict[str, Any]] = []
        for record, score in final_ranked:
            content = ""
            try:
                blob_bytes = await walrus.get_blob(record.walrus_blob_id)
                payload = json.loads(blob_bytes.decode("utf-8"))
                raw_content = payload.get("content", "")
                meta = payload.get("metadata", {})
                is_encrypted = meta.get("extra", {}).get(
                    "is_encrypted", False
                )

                if is_encrypted and encryption_key:
                    from membrane.security import decrypt_content
                    try:
                        content = decrypt_content(raw_content, encryption_key)
                    except Exception:
                        content = "[encrypted — decryption failed]"
                else:
                    content = raw_content
            except Exception:
                logger.warning(
                    "Failed to fetch Walrus blob for memory %s",
                    record.memory_id,
                    exc_info=True,
                )
                content = "[content unavailable]"

            results.append({
                "memory_id": record.memory_id,
                "content": content,
                "namespace": record.namespace,
                "owner": record.owner,
                "tags": json.loads(record.tags),
                "relevance_score": round(score, 4),
                "walrus_blob_id": record.walrus_blob_id,
                "created_at": record.timestamp,
            })

        return results

    async def _metadata_filter(
        self,
        db: asyncpg.Connection,
        namespace: str | None = None,
        owner: str | None = None,
        allowed_user: str | None = None,
        tags: list[str] | None = None,
    ) -> list[MemoryRecord]:
        """Query PostgreSQL for candidate memory records."""
        from membrane.memory_manager import MemoryManager, _bytes_to_embedding
        from membrane.models import MemoryRecord

        query = "SELECT * FROM memories WHERE 1=1"
        params: list[Any] = []

        if namespace:
            params.append(namespace)
            query += f" AND namespace = ${len(params)}"
        if owner and allowed_user:
            params.extend([owner, f'%"{allowed_user}"%'])
            query += f" AND (owner = ${len(params)-1} OR allowed_users LIKE ${len(params)})"
        elif owner:
            params.append(owner)
            query += f" AND owner = ${len(params)}"
        elif allowed_user:
            params.append(f'%"{allowed_user}"%')
            query += f" AND allowed_users LIKE ${len(params)}"
        if tags:
            for tag in tags:
                params.append(f'%"{tag}"%')
                query += f" AND tags LIKE ${len(params)}"

        rows = await db.fetch(query, *params)

        records: list[MemoryRecord] = []
        for row in rows:
            embedding = None
            raw_emb = row["embedding"]
            if raw_emb is not None:
                embedding = _bytes_to_embedding(raw_emb)

            records.append(MemoryRecord(
                memory_id=row["memory_id"],
                namespace=row["namespace"],
                owner=row["owner"],
                visibility=dict(row).get("visibility", "private"),
                allowed_agents=dict(row).get("allowed_agents", "[]"),
                allowed_users=dict(row).get("allowed_users", "[]"),
                tags=row["tags"],
                timestamp=row["timestamp"],
                walrus_blob_id=row["walrus_blob_id"],
                content_hash=row["content_hash"],
                proof_id=row["proof_id"],
                embedding=embedding,
            ))

        return records
