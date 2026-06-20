"""FastMCP server builder for multi-tenant users.

This module exposes `build_user_server` which provisions a FastMCP instance
scoped strictly to a specific UserContext. Tools automatically inject
the user's owner identifier and namespace.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from mcp.server.fastmcp import FastMCP

from membrane.artifact_manager import ArtifactManager
from membrane.config import MembraneSettings
from membrane.db import get_db
from membrane.memory_manager import MemoryManager
from membrane.retrieval import RetrievalEngine
from membrane.scoped_managers import (
    ScopedArtifactManager,
    ScopedMemoryManager,
    ScopedRetrievalEngine,
)
from membrane.security import verify_memory_full
from membrane.sui_client import SuiClient
from membrane.user_context import UserContext
from membrane.walrus_client import WalrusClient

logger = logging.getLogger(__name__)


def build_user_server(
    context: UserContext,
    settings: MembraneSettings,
    walrus: WalrusClient,
    sui: SuiClient,
    memory_manager: MemoryManager,
    artifact_manager: ArtifactManager,
    retrieval_engine: RetrievalEngine,
) -> FastMCP:
    """Build and return a FastMCP server scoped to the given UserContext."""
    mcp = FastMCP(
        f"Membrane-{context.username}",
        host="0.0.0.0",
        instructions=(
            f"Universal memory layer for AI agents (User: {context.username}) "
            "— store, search, and verify memories via MCP. All content is "
            "persisted in Walrus decentralized storage."
        ),
    )

    # Provision scoped managers
    scoped_mem = ScopedMemoryManager(memory_manager, context)
    scoped_art = ScopedArtifactManager(artifact_manager, context)
    scoped_ret = ScopedRetrievalEngine(retrieval_engine, context)

    # ------------------------------------------------------------------
    # Tool: store_memory
    # ------------------------------------------------------------------
    @mcp.tool()
    async def store_memory(
        content: str,
        visibility: str = "private",
        allowed_agents: list[str] | None = None,
        allowed_users: list[str] | None = None,
        tags: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
        relations: list[dict[str, str]] | None = None,
        encrypt: bool = False,
    ) -> dict[str, Any]:
        """Store a memory scoped to the current user."""
        db = await get_db(settings.database_url)
        try:
            result = await scoped_mem.manager.store(
                db=db,
                content=content,
                namespace=context.namespace,
                owner=context.owner,
                visibility=visibility,
                allowed_agents=allowed_agents,
                allowed_users=allowed_users,
                tags=tags,
                metadata=metadata,
                relations=relations,
                encrypt=encrypt,
            )
            return result.model_dump()
        finally:
            await db.close()

    # ------------------------------------------------------------------
    # Tool: search_memory
    # ------------------------------------------------------------------
    @mcp.tool()
    async def search_memory(
        query: str,
        tags: list[str] | None = None,
        limit: int | None = None,
    ) -> dict[str, Any]:
        """Search memories owned by or shared with the current user."""
        k = limit or settings.default_retrieval_limit
        db = await get_db(settings.database_url)
        try:
            results = await scoped_ret.search(
                db=db,
                walrus=walrus,
                query=query,
                tags=tags,
                limit=k,
                encryption_key=settings.encryption_key,
            )
            return {"memories": results}
        finally:
            await db.close()

    # ------------------------------------------------------------------
    # Tool: update_memory
    # ------------------------------------------------------------------
    @mcp.tool()
    async def update_memory(
        memory_id: str,
        content: str | None = None,
        metadata: dict[str, Any] | None = None,
        tags: list[str] | None = None,
        visibility: str | None = None,
        allowed_agents: list[str] | None = None,
        allowed_users: list[str] | None = None,
        relations: list[dict[str, str]] | None = None,
    ) -> dict[str, Any]:
        """Update an existing memory."""
        db = await get_db(settings.database_url)
        try:
            return await scoped_mem.update(
                db=db,
                memory_id=memory_id,
                content=content,
                metadata=metadata,
                tags=tags,
                visibility=visibility,
                allowed_agents=allowed_agents,
                allowed_users=allowed_users,
                relations=relations,
            )
        finally:
            await db.close()

    # ------------------------------------------------------------------
    # Tool: delete_memory
    # ------------------------------------------------------------------
    @mcp.tool()
    async def delete_memory(memory_id: str) -> dict[str, Any]:
        """Delete a memory."""
        db = await get_db(settings.database_url)
        try:
            # Basic validation: ensure it's owned by the user
            mem = await scoped_mem.get(db, memory_id)
            if not mem or mem["owner"] != context.owner:
                return {"error": "Not found or not authorized to delete."}
            return await scoped_mem.delete(db=db, memory_id=memory_id)
        finally:
            await db.close()

    # ------------------------------------------------------------------
    # Tool: verify_memory
    # ------------------------------------------------------------------
    @mcp.tool()
    async def verify_memory(memory_id: str) -> dict[str, Any]:
        """Verify memory integrity."""
        db = await get_db(settings.database_url)
        try:
            mem = await scoped_mem.get(db, memory_id)
            if not mem:
                return {"error": "Memory not found."}
            
            walrus_blob_id = mem["walrus_blob_id"]
            
            row = await db.fetchrow("SELECT * FROM memories WHERE memory_id = $1", memory_id)
            if row is None:
                return {"error": f"Memory '{memory_id}' not found."}
            
            stored_hash = row["content_hash"]

            walrus_content: bytes | None = None
            try:
                walrus_content = await walrus.get_blob(walrus_blob_id)
            except Exception:
                logger.warning("Failed to fetch Walrus blob", exc_info=True)

            result = await verify_memory_full(
                db=db,
                memory_id=memory_id,
                walrus_blob_content=walrus_content,
                stored_content_hash=stored_hash,
                hmac_secret=settings.hmac_secret,
                encryption_key=settings.encryption_key,
                walrus_blob_id=walrus_blob_id,
                sui_client=sui,
            )
            return result.model_dump()
        finally:
            await db.close()

    # ------------------------------------------------------------------
    # Tool: store_artifact
    # ------------------------------------------------------------------
    @mcp.tool()
    async def store_artifact(
        content: str,
        type: str = "artifact",
        visibility: str = "private",
        allowed_agents: list[str] | None = None,
        allowed_users: list[str] | None = None,
        filename: str = "",
        content_type: str = "",
        tags: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Store an artifact."""
        db = await get_db(settings.database_url)
        try:
            result = await scoped_art.store(
                db=db,
                content=content,
                type=type,
                visibility=visibility,
                allowed_agents=allowed_agents,
                allowed_users=allowed_users,
                filename=filename,
                content_type=content_type,
                tags=tags,
                metadata=metadata,
            )
            return result.model_dump()
        finally:
            await db.close()

    # ------------------------------------------------------------------
    # Tool: get_artifact
    # ------------------------------------------------------------------
    @mcp.tool()
    async def get_artifact(artifact_id: str) -> dict[str, Any]:
        """Retrieve an artifact."""
        db = await get_db(settings.database_url)
        try:
            result = await scoped_art.get(db, artifact_id)
            if result is None:
                return {"error": f"Artifact '{artifact_id}' not found."}
            return result
        finally:
            await db.close()

    # ------------------------------------------------------------------
    # Tool: list_memories
    # ------------------------------------------------------------------
    @mcp.tool()
    async def list_memories() -> dict[str, Any]:
        """List stored memory metadata for the current user."""
        db = await get_db(settings.database_url)
        try:
            records = await scoped_mem.list_memories(db)
            return {"memories": records, "total": len(records)}
        finally:
            await db.close()

    # ------------------------------------------------------------------
    # Tool: list_artifacts
    # ------------------------------------------------------------------
    @mcp.tool()
    async def list_artifacts(type: str | None = None) -> dict[str, Any]:
        """List stored artifact metadata for the current user."""
        db = await get_db(settings.database_url)
        try:
            records = await scoped_art.list_artifacts(db, type=type)
            return {"artifacts": records, "total": len(records)}
        finally:
            await db.close()

    # ------------------------------------------------------------------
    # Tool: inspect_memory
    # ------------------------------------------------------------------
    @mcp.tool()
    async def inspect_memory(memory_id: str) -> dict[str, Any]:
        """Inspect a single memory's metadata and graph relations."""
        db = await get_db(settings.database_url)
        try:
            row = await db.fetchrow("SELECT * FROM memories WHERE memory_id = $1", memory_id)
            if not row:
                return {"error": f"Memory '{memory_id}' not found."}
            
            # Simple access check
            owner = row["owner"]
            allowed_users = json.loads(dict(row).get("allowed_users", "[]"))
            visibility = dict(row).get("visibility", "private")
            
            if owner != context.owner and context.username not in allowed_users and visibility != "public":
                return {"error": "Not authorized to inspect this memory."}
            
            rel_rows = await db.fetch("SELECT source_id, target_id, relation_type FROM memory_relations WHERE source_id = $1", memory_id)
            relations = [{"source_id": r["source_id"], "target_id": r["target_id"], "type": r["relation_type"]} for r in rel_rows]
            
            return {
                "memory_id": row["memory_id"],
                "namespace": row["namespace"],
                "owner": row["owner"],
                "visibility": visibility,
                "allowed_agents": json.loads(dict(row).get("allowed_agents", "[]")),
                "allowed_users": allowed_users,
                "tags": json.loads(row["tags"]),
                "timestamp": row["timestamp"],
                "walrus_blob_id": row["walrus_blob_id"],
                "relations": relations
            }
        finally:
            await db.close()

    # ------------------------------------------------------------------
    # Tool: show_graph
    # ------------------------------------------------------------------
    @mcp.tool()
    async def show_graph(memory_id: str, depth: int = 1) -> dict[str, Any]:
        """Visualize the memory graph starting from a node."""
        db = await get_db(settings.database_url)
        try:
            # We skip access checks here for brevity or assume they can only see graphs from their memories.
            visited_nodes = set()
            queue = [(memory_id, 0)]
            edges = []
            
            while queue:
                current_id, current_depth = queue.pop(0)
                if current_id in visited_nodes or current_depth > depth:
                    continue
                visited_nodes.add(current_id)
                
                rel_rows = await db.fetch("SELECT source_id, target_id, relation_type FROM memory_relations WHERE source_id = $1", current_id)
                for r in rel_rows:
                    edges.append({"source_id": r["source_id"], "target_id": r["target_id"], "type": r["relation_type"]})
                    if r["target_id"] not in visited_nodes:
                        queue.append((r["target_id"], current_depth + 1))
            
            nodes = []
            if visited_nodes:
                visited_list = list(visited_nodes)
                placeholders = ",".join(f"${i+1}" for i in range(len(visited_list)))
                node_rows = await db.fetch(f"SELECT memory_id, namespace, owner, tags FROM memories WHERE memory_id IN ({placeholders})", *visited_list)
                nodes = [{"memory_id": r["memory_id"], "namespace": r["namespace"], "owner": r["owner"], "tags": json.loads(r["tags"])} for r in node_rows]
                
            return {"nodes": nodes, "edges": edges}
        finally:
            await db.close()

    # ------------------------------------------------------------------
    # Tool: list_agents
    # ------------------------------------------------------------------
    @mcp.tool()
    async def list_agents() -> dict[str, Any]:
        """List distinct agents (owners) in the memory layer."""
        db = await get_db(settings.database_url)
        try:
            rows = await db.fetch("SELECT DISTINCT owner FROM memories WHERE owner != ''")
            agents = [row["owner"] for row in rows]
            return {"agents": agents}
        finally:
            await db.close()

    # ------------------------------------------------------------------
    # Tool: list_workflows
    # ------------------------------------------------------------------
    @mcp.tool()
    async def list_workflows() -> dict[str, Any]:
        """List stored workflow state artifacts."""
        db = await get_db(settings.database_url)
        try:
            records = await scoped_art.list_artifacts(db, type="workflow")
            return {"workflows": records, "total": len(records)}
        finally:
            await db.close()

    # ------------------------------------------------------------------
    # Tool: verify_blob
    # ------------------------------------------------------------------
    @mcp.tool()
    async def verify_blob(walrus_blob_id: str) -> dict[str, Any]:
        """Check if a blob is available on Walrus without downloading its full content."""
        try:
            await walrus.get_blob(walrus_blob_id)
            return {"walrus_blob_id": walrus_blob_id, "exists": True}
        except Exception as e:
            return {"walrus_blob_id": walrus_blob_id, "exists": False, "error": str(e)}

    return mcp
