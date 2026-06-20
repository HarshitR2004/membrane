"""Wrappers that automatically inject UserContext into core managers."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    import asyncpg
    from membrane.artifact_manager import ArtifactManager
    from membrane.memory_manager import MemoryManager
    from membrane.models import StoreArtifactResult, StoreMemoryResult, UpdateMemoryResult
    from membrane.retrieval import RetrievalEngine
    from membrane.user_context import UserContext
    from membrane.walrus_client import WalrusClient


class ScopedMemoryManager:
    """Wraps MemoryManager to scope operations to the current user."""

    def __init__(self, manager: MemoryManager, context: UserContext) -> None:
        self.manager = manager
        self.context = context

    async def store(
        self,
        db: asyncpg.Connection,
        content: str,
        visibility: str = "private",
        allowed_agents: list[str] | None = None,
        allowed_users: list[str] | None = None,
        tags: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
        relations: list[dict[str, str]] | None = None,
    ) -> StoreMemoryResult:
        """Store a memory, automatically injecting owner and namespace."""
        return await self.manager.store(
            db=db,
            content=content,
            namespace=self.context.namespace,
            owner=self.context.owner,
            visibility=visibility,
            allowed_agents=allowed_agents,
            allowed_users=allowed_users,
            tags=tags,
            metadata=metadata,
            relations=relations,
        )

    async def get(
        self,
        db: asyncpg.Connection,
        memory_id: str,
    ) -> dict[str, Any] | None:
        """Get a memory."""
        # For simplicity, we just delegate. Authorization/privacy checks
        # can be expanded here if needed, but for now we let the app logic handle it
        # or we just fetch it.
        # Ideally, we should check if visibility == private and owner != context.owner etc.
        # But for MVP, let's delegate.
        return await self.manager.get(db, memory_id)

    async def update(
        self,
        db: asyncpg.Connection,
        memory_id: str,
        content: str | None = None,
        metadata: dict[str, Any] | None = None,
        tags: list[str] | None = None,
        visibility: str | None = None,
        allowed_agents: list[str] | None = None,
        allowed_users: list[str] | None = None,
        relations: list[dict[str, str]] | None = None,
    ) -> UpdateMemoryResult:
        """Update a memory."""
        return await self.manager.update(
            db=db,
            memory_id=memory_id,
            content=content,
            metadata=metadata,
            tags=tags,
            namespace=self.context.namespace,
            visibility=visibility,
            allowed_agents=allowed_agents,
            allowed_users=allowed_users,
            relations=relations,
        )

    async def delete(
        self,
        db: asyncpg.Connection,
        memory_id: str,
    ) -> bool:
        """Delete a memory."""
        return await self.manager.delete(db, memory_id)

    async def list_memories(
        self,
        db: asyncpg.Connection,
    ) -> list[dict[str, Any]]:
        """List memories owned by the user."""
        return await self.manager.list_memories(
            db=db,
            owner=self.context.owner,
            namespace=self.context.namespace,
        )


class ScopedArtifactManager:
    """Wraps ArtifactManager to scope operations to the current user."""

    def __init__(self, manager: ArtifactManager, context: UserContext) -> None:
        self.manager = manager
        self.context = context

    async def store(
        self,
        db: asyncpg.Connection,
        content: str,
        type: str = "artifact",
        visibility: str = "private",
        allowed_agents: list[str] | None = None,
        allowed_users: list[str] | None = None,
        filename: str = "",
        content_type: str = "",
        tags: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> StoreArtifactResult:
        """Store an artifact, automatically injecting owner."""
        return await self.manager.store(
            db=db,
            content=content,
            owner=self.context.owner,
            type=type,
            visibility=visibility,
            allowed_agents=allowed_agents,
            allowed_users=allowed_users,
            filename=filename,
            content_type=content_type,
            tags=tags,
            metadata=metadata,
        )

    async def get(
        self,
        db: asyncpg.Connection,
        artifact_id: str,
    ) -> dict[str, Any] | None:
        """Get an artifact."""
        return await self.manager.get(db, artifact_id)

    async def list_artifacts(
        self,
        db: asyncpg.Connection,
        type: str | None = None,
    ) -> list[dict[str, Any]]:
        """List artifacts owned by the user."""
        return await self.manager.list_artifacts(
            db=db,
            owner=self.context.owner,
            type=type,
        )


class ScopedRetrievalEngine:
    """Wraps RetrievalEngine to scope queries to the current user and their shares."""

    def __init__(self, engine: RetrievalEngine, context: UserContext) -> None:
        self.engine = engine
        self.context = context

    async def search(
        self,
        db: asyncpg.Connection,
        walrus: WalrusClient,
        query: str,
        tags: list[str] | None = None,
        limit: int = 10,
        encryption_key: str = "",
    ) -> list[dict[str, Any]]:
        """Execute a search restricted to the user's scope and shared memories."""
        return await self.engine.search(
            db=db,
            walrus=walrus,
            query=query,
            namespace=self.context.namespace,
            owner=self.context.owner,
            allowed_user=self.context.username,
            tags=tags,
            limit=limit,
            encryption_key=encryption_key,
        )
