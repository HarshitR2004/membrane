"""Memory Manager — orchestrates the full memory lifecycle.

Coordinates Walrus uploads, PostgreSQL metadata writes, Sui proof recording,
and background embedding generation.  This replaces the old ``memory.py``
module which stored content directly in PostgreSQL.
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any

import asyncpg
import numpy as np

from membrane.config import MembraneSettings
from membrane.models import (
    ArtifactRecord,
    MemoryMetadata,
    MemoryPayload,
    MemoryRecord,
    Relation,
    StoreMemoryResult,
    UpdateMemoryResult,
)
from membrane.security import (
    decrypt_content,
    encrypt_content,
    generate_content_hash,
    generate_hmac,
    store_proof,
    delete_proof,
)
from membrane.sui_client import SuiClient
from membrane.walrus_client import WalrusClient, WalrusError

logger = logging.getLogger(__name__)


def _now_iso() -> str:
    """Return the current UTC time as an ISO-8601 string."""
    return datetime.now(timezone.utc).isoformat()


def _embedding_to_bytes(embedding: list[float] | np.ndarray) -> bytes:
    """Serialize a float vector to raw bytes for BYTEA storage."""
    return np.array(embedding, dtype=np.float32).tobytes()


def _bytes_to_embedding(data: bytes) -> list[float]:
    """Deserialize raw bytes back to a list of floats."""
    return np.frombuffer(data, dtype=np.float32).tolist()


class MemoryManager:
    """Orchestrates memory lifecycle: Walrus storage, metadata, proofs.

    Write flow:
      1. Build ``MemoryPayload`` JSON
      2. Generate SHA-256 hash of **plaintext** content
      3. Optionally encrypt content
      4. Serialise payload → bytes
      5. Upload to Walrus → ``blob_id``
      6. Record proof on Sui (best-effort)
      7. Save metadata row in PostgreSQL (no content)
      8. Return result

    Read flow:
      1. Look up metadata in PostgreSQL
      2. Fetch blob from Walrus using ``walrus_blob_id``
      3. Deserialise JSON payload
      4. Optionally decrypt content
      5. Return full memory
    """

    def __init__(
        self,
        walrus: WalrusClient,
        sui: SuiClient,
        settings: MembraneSettings,
    ) -> None:
        self._walrus = walrus
        self._sui = sui
        self._settings = settings

    # ------------------------------------------------------------------
    # Store
    # ------------------------------------------------------------------

    async def store(
        self,
        db: asyncpg.Connection,
        content: str,
        namespace: str | None = None,
        owner: str | None = None,
        visibility: str = "private",
        allowed_agents: list[str] | None = None,
        allowed_users: list[str] | None = None,
        tags: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
        relations: list[dict[str, str]] | None = None,
        encrypt: bool = False,
    ) -> StoreMemoryResult:
        """Store a new memory in Walrus with metadata in PostgreSQL."""
        memory_id = str(uuid.uuid4())
        now = _now_iso()
        ns = namespace or self._settings.default_namespace
        own = owner or self._settings.default_owner
        tag_list = tags or []
        allowed_agents_list = allowed_agents or []
        allowed_users_list = allowed_users or []
        extra = metadata or {}
        rel_list = [Relation(**r) for r in (relations or [])]

        # 1. Content hash (always computed on plaintext)
        content_hash = generate_content_hash(content)

        # 2. Optionally encrypt
        stored_content = content
        if encrypt:
            stored_content = encrypt_content(content, self._settings.encryption_key)

        # 3. Build Walrus payload
        payload = MemoryPayload(
            memory_id=memory_id,
            namespace=ns,
            owner=own,
            visibility=visibility,
            allowed_agents=allowed_agents_list,
            allowed_users=allowed_users_list,
            created_at=now,
            updated_at=now,
            type="memory",
            content=stored_content,
            metadata=MemoryMetadata(
                tags=tag_list,
                source=extra.get("source", "agent"),
                relations=rel_list,
                extra={**extra, "is_encrypted": encrypt},
            ),
        )

        # 4. Upload to Walrus
        payload_bytes = payload.model_dump_json().encode("utf-8")
        walrus_result = await self._walrus.store_blob(payload_bytes)
        blob_id = walrus_result.blob_id

        # 5. Save metadata in PostgreSQL first (no content!)
        #    Must happen before proof insertion due to FK constraint.
        proof_id: str | None = None
        await db.execute(
            """
            INSERT INTO memories
                (memory_id, namespace, owner, visibility, allowed_agents, allowed_users, tags, timestamp,
                 walrus_blob_id, content_hash, proof_id)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
            """,
            memory_id, ns, own, visibility, json.dumps(allowed_agents_list), json.dumps(allowed_users_list), json.dumps(tag_list), now,
            blob_id, content_hash, proof_id
        )

        for rel in rel_list:
            await db.execute(
                "INSERT INTO memory_relations (source_id, target_id, relation_type) VALUES ($1, $2, $3)",
                memory_id, rel.target_id, rel.type
            )

        # 6. Record proof on Sui (best-effort)
        if self._sui.enabled:
            proof_result = await self._sui.record_proof(
                memory_id=memory_id,
                content_hash=content_hash,
                walrus_blob_id=blob_id,
            )
            if proof_result is not None:
                proof_id = proof_result.proof_id
                await store_proof(
                    db,
                    proof_id=proof_result.proof_id,
                    sui_tx_hash=proof_result.tx_hash,
                    memory_id=memory_id,
                    content_hash=content_hash,
                )
                # Update the memory row with the proof_id
                await db.execute(
                    "UPDATE memories SET proof_id = $1 WHERE memory_id = $2",
                    proof_id, memory_id
                )

        logger.info(
            "Memory stored: id=%s blob=%s namespace=%s",
            memory_id, blob_id, ns,
        )

        return StoreMemoryResult(
            memory_id=memory_id,
            walrus_blob_id=blob_id,
            namespace=ns,
            status="stored",
        )

    # ------------------------------------------------------------------
    # Get (by ID)
    # ------------------------------------------------------------------

    async def get(
        self,
        db: asyncpg.Connection,
        memory_id: str,
    ) -> dict[str, Any] | None:
        """Retrieve a memory by ID — fetches content from Walrus."""
        # 1. Metadata from PostgreSQL
        row = await db.fetchrow(
            "SELECT * FROM memories WHERE memory_id = $1", memory_id
        )
        if row is None:
            return None

        record = self._row_to_record(row)

        # 2. Fetch blob from Walrus
        try:
            blob_bytes = await self._walrus.get_blob(record.walrus_blob_id)
        except WalrusError as exc:
            logger.warning("Failed to fetch Walrus blob: %s", exc)
            return {
                "memory_id": record.memory_id,
                "error": f"Failed to fetch content from Walrus: {exc}",
                "namespace": record.namespace,
                "owner": record.owner,
                "walrus_blob_id": record.walrus_blob_id,
            }

        # 3. Parse payload
        payload = json.loads(blob_bytes.decode("utf-8"))
        raw_content = payload.get("content", "")
        meta = payload.get("metadata", {})
        is_encrypted = meta.get("extra", {}).get("is_encrypted", False)

        # 4. Decrypt if needed
        display_content = raw_content
        if is_encrypted:
            try:
                display_content = decrypt_content(
                    raw_content, self._settings.encryption_key
                )
            except Exception:
                display_content = "[encrypted — decryption failed]"

        return {
            "memory_id": record.memory_id,
            "content": display_content,
            "namespace": record.namespace,
            "owner": record.owner,
            "tags": json.loads(record.tags),
            "metadata": meta,
            "walrus_blob_id": record.walrus_blob_id,
            "content_hash": record.content_hash,
            "is_encrypted": is_encrypted,
            "created_at": payload.get("created_at", record.timestamp),
            "updated_at": payload.get("updated_at", record.timestamp),
            "visibility": dict(row).get("visibility", "private"),
            "allowed_agents": json.loads(dict(row).get("allowed_agents", "[]")),
            "allowed_users": json.loads(dict(row).get("allowed_users", "[]")),
        }

    # ------------------------------------------------------------------
    # Update
    # ------------------------------------------------------------------

    async def update(
        self,
        db: asyncpg.Connection,
        memory_id: str,
        content: str | None = None,
        metadata: dict[str, Any] | None = None,
        tags: list[str] | None = None,
        namespace: str | None = None,
        visibility: str | None = None,
        allowed_agents: list[str] | None = None,
        allowed_users: list[str] | None = None,
        relations: list[dict[str, str]] | None = None,
    ) -> dict[str, Any]:
        """Update an existing memory — re-uploads to Walrus."""
        # 1. Get current metadata
        row = await db.fetchrow(
            "SELECT * FROM memories WHERE memory_id = $1", memory_id
        )
        if row is None:
            return {"error": f"Memory '{memory_id}' not found."}

        record = self._row_to_record(row)

        # 2. Fetch current payload from Walrus
        try:
            blob_bytes = await self._walrus.get_blob(record.walrus_blob_id)
        except WalrusError as exc:
            return {"error": f"Failed to fetch current content from Walrus: {exc}"}

        payload_dict = json.loads(blob_bytes.decode("utf-8"))
        old_meta = payload_dict.get("metadata", {})
        is_encrypted = old_meta.get("extra", {}).get("is_encrypted", False)

        # 3. Resolve new content
        old_content = payload_dict.get("content", "")
        if content is not None:
            new_plaintext = content
        elif is_encrypted:
            try:
                new_plaintext = decrypt_content(
                    old_content, self._settings.encryption_key
                )
            except Exception:
                return {"error": "Failed to decrypt existing content for update."}
        else:
            new_plaintext = old_content

        # 4. Build updated payload
        now = _now_iso()
        new_content_hash = generate_content_hash(new_plaintext)

        stored_content = new_plaintext
        if is_encrypted:
            stored_content = encrypt_content(
                new_plaintext, self._settings.encryption_key
            )

        new_ns = namespace or record.namespace
        new_tags = tags if tags is not None else json.loads(record.tags)
        new_visibility = visibility if visibility is not None else dict(row).get("visibility", "private")
        
        if allowed_agents is not None:
            new_allowed_agents = allowed_agents
        else:
            try:
                new_allowed_agents = json.loads(dict(row).get("allowed_agents", "[]"))
            except Exception:
                new_allowed_agents = []

        if allowed_users is not None:
            new_allowed_users = allowed_users
        else:
            try:
                new_allowed_users = json.loads(dict(row).get("allowed_users", "[]"))
            except Exception:
                new_allowed_users = []

        if relations is not None:
            new_relations = [Relation(**r) for r in relations]
        else:
            # Fallback to parsing from payload metadata, which models.py uses
            try:
                raw_rels = old_meta.get("relations", [])
                new_relations = [Relation(**r) if isinstance(r, dict) else r for r in raw_rels]
            except Exception:
                new_relations = []

        new_extra = metadata if metadata is not None else old_meta.get("extra", {})
        if isinstance(new_extra, dict):
            new_extra["is_encrypted"] = is_encrypted

        updated_payload = MemoryPayload(
            memory_id=memory_id,
            namespace=new_ns,
            owner=record.owner,
            visibility=new_visibility,
            allowed_agents=new_allowed_agents,
            allowed_users=new_allowed_users,
            created_at=payload_dict.get("created_at", record.timestamp),
            updated_at=now,
            type="memory",
            content=stored_content,
            metadata=MemoryMetadata(
                tags=new_tags,
                source=old_meta.get("source", "agent"),
                relations=new_relations,
                extra=new_extra,
            ),
        )

        # 5. Re-upload to Walrus (new blob)
        payload_bytes = updated_payload.model_dump_json().encode("utf-8")
        walrus_result = await self._walrus.store_blob(payload_bytes)
        new_blob_id = walrus_result.blob_id

        # 6. Record new proof on Sui
        proof_id: str | None = record.proof_id
        if self._sui.enabled:
            proof_result = await self._sui.record_proof(
                memory_id=memory_id,
                content_hash=new_content_hash,
                walrus_blob_id=new_blob_id,
            )
            if proof_result is not None:
                proof_id = proof_result.proof_id
                # Delete old proof, store new
                await delete_proof(db, memory_id)
                await store_proof(
                    db,
                    proof_id=proof_result.proof_id,
                    sui_tx_hash=proof_result.tx_hash,
                    memory_id=memory_id,
                    content_hash=new_content_hash,
                )

        # 7. Update metadata in PostgreSQL
        await db.execute(
            """
            UPDATE memories SET
                namespace = $1, visibility = $2, allowed_agents = $3, allowed_users = $4, tags = $5, walrus_blob_id = $6,
                content_hash = $7, proof_id = $8, timestamp = $9
            WHERE memory_id = $10
            """,
            new_ns, new_visibility, json.dumps(new_allowed_agents), json.dumps(new_allowed_users), json.dumps(new_tags), new_blob_id,
            new_content_hash, proof_id, now, memory_id
        )

        if relations is not None:
            await db.execute("DELETE FROM memory_relations WHERE source_id = $1", memory_id)
            for rel in new_relations:
                await db.execute(
                    "INSERT INTO memory_relations (source_id, target_id, relation_type) VALUES ($1, $2, $3)",
                    memory_id, rel.target_id, rel.type
                )

        return {
            "memory_id": memory_id,
            "walrus_blob_id": new_blob_id,
            "status": "updated",
        }

    # ------------------------------------------------------------------
    # Delete
    # ------------------------------------------------------------------

    async def delete(
        self,
        db: asyncpg.Connection,
        memory_id: str,
    ) -> dict[str, Any]:
        """Delete a memory's metadata and proof. Walrus blobs expire naturally."""
        row = await db.fetchrow(
            "SELECT memory_id FROM memories WHERE memory_id = $1", memory_id
        )
        if row is None:
            return {"error": f"Memory '{memory_id}' not found."}

        # Delete proof
        await delete_proof(db, memory_id)

        # Delete metadata
        await db.execute(
            "DELETE FROM memories WHERE memory_id = $1", memory_id
        )

        logger.info("Memory deleted: %s", memory_id)
        return {"status": "deleted"}

    # ------------------------------------------------------------------
    # List
    # ------------------------------------------------------------------

    async def list_memories(
        self,
        db: asyncpg.Connection,
        namespace: str | None = None,
        owner: str | None = None,
    ) -> list[dict[str, Any]]:
        """List memory metadata records (without fetching Walrus content)."""
        query = "SELECT * FROM memories WHERE 1=1"
        params: list[Any] = []

        if namespace:
            params.append(namespace)
            query += f" AND namespace = ${len(params)}"
        if owner:
            params.append(owner)
            query += f" AND owner = ${len(params)}"

        query += " ORDER BY timestamp DESC"

        rows = await db.fetch(query, *params)

        return [
            {
                "memory_id": row["memory_id"],
                "namespace": row["namespace"],
                "owner": row["owner"],
                "visibility": dict(row).get("visibility", "private"),
                "allowed_agents": json.loads(dict(row).get("allowed_agents", "[]")),
                "allowed_users": json.loads(dict(row).get("allowed_users", "[]")),
                "tags": json.loads(row["tags"]),
                "timestamp": row["timestamp"],
                "walrus_blob_id": row["walrus_blob_id"],
                "content_hash": row["content_hash"],
                "proof_id": row["proof_id"],
            }
            for row in rows
        ]

    # ------------------------------------------------------------------
    # Embedding helpers (for async generation)
    # ------------------------------------------------------------------

    async def save_embedding(
        self,
        db: asyncpg.Connection,
        memory_id: str,
        embedding: list[float] | np.ndarray,
    ) -> None:
        """Persist an embedding vector to the metadata row."""
        emb_bytes = _embedding_to_bytes(embedding)
        await db.execute(
            "UPDATE memories SET embedding = $1 WHERE memory_id = $2",
            emb_bytes, memory_id
        )

    async def get_all_records_with_embeddings(
        self,
        db: asyncpg.Connection,
        namespace: str | None = None,
        owner: str | None = None,
        tags: list[str] | None = None,
    ) -> list[MemoryRecord]:
        """Fetch metadata rows for filtering/reranking."""
        query = "SELECT * FROM memories WHERE 1=1"
        params: list[Any] = []

        if namespace:
            params.append(namespace)
            query += f" AND namespace = ${len(params)}"
        if owner:
            params.append(owner)
            query += f" AND owner = ${len(params)}"
        if tags:
            for tag in tags:
                params.append(f"%{tag}%")
                query += f" AND tags LIKE ${len(params)}"

        rows = await db.fetch(query, *params)
        return [self._row_to_record(r) for r in rows]

    # ------------------------------------------------------------------
    # Row mapping
    # ------------------------------------------------------------------

    @staticmethod
    def _row_to_record(row: asyncpg.Record) -> MemoryRecord:
        """Convert a database row to a MemoryRecord."""
        embedding = None
        raw_emb = row["embedding"]
        if raw_emb is not None:
            embedding = _bytes_to_embedding(raw_emb)

        return MemoryRecord(
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
