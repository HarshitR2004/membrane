"""Pydantic data models shared across Membrane layers.

Models are split into three categories:
  • Walrus payload models — serialised to JSON and stored in Walrus blobs.
  • PostgreSQL metadata models — lightweight records kept in the local database.
  • MCP response models   — returned to callers of MCP tools.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Walrus payload models (stored as blobs)
# ---------------------------------------------------------------------------

class Relation(BaseModel):
    """Relationship to another memory."""

    target_id: str
    type: str


class MemoryMetadata(BaseModel):
    """Metadata embedded inside a Walrus memory payload."""

    tags: list[str] = Field(default_factory=list)
    source: str = "agent"
    relations: list[Relation] = Field(default_factory=list)
    extra: dict[str, Any] = Field(default_factory=dict)


class MemoryPayload(BaseModel):
    """The canonical memory object serialised to JSON and stored in Walrus."""

    memory_id: str
    namespace: str = "default"
    owner: str = ""
    visibility: str = "private"
    allowed_agents: list[str] = Field(default_factory=list)
    allowed_users: list[str] = Field(default_factory=list)
    created_at: str = ""
    updated_at: str = ""
    type: str = "memory"
    content: str = ""
    metadata: MemoryMetadata = Field(default_factory=MemoryMetadata)


class ArtifactPayload(BaseModel):
    """Artifact object serialised to JSON and stored in Walrus."""

    artifact_id: str
    owner: str = ""
    visibility: str = "private"
    allowed_agents: list[str] = Field(default_factory=list)
    allowed_users: list[str] = Field(default_factory=list)
    filename: str = ""
    content_type: str = ""
    created_at: str = ""
    type: str = "artifact"
    content: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# PostgreSQL metadata models (no content — content lives in Walrus)
# ---------------------------------------------------------------------------

class MemoryRecord(BaseModel):
    """Local metadata record for a memory (PostgreSQL row)."""

    memory_id: str
    namespace: str = "default"
    owner: str = ""
    visibility: str = "private"
    allowed_agents: str = "[]"   # JSON-encoded list
    allowed_users: str = "[]"    # JSON-encoded list
    tags: str = "[]"           # JSON-encoded list
    timestamp: str = ""
    walrus_blob_id: str = ""
    content_hash: str = ""
    proof_id: str | None = None
    # Embedding stored as raw bytes in DB; loaded as list[float] when needed
    embedding: list[float] | None = None


class ArtifactRecord(BaseModel):
    """Local metadata record for an artifact (PostgreSQL row)."""

    artifact_id: str
    walrus_blob_id: str = ""
    owner: str = ""
    visibility: str = "private"
    allowed_agents: str = "[]"   # JSON-encoded list
    allowed_users: str = "[]"    # JSON-encoded list
    type: str = "artifact"
    filename: str = ""
    content_type: str = ""
    tags: str = "[]"
    timestamp: str = ""
    content_hash: str = ""


class ProofRecord(BaseModel):
    """On-chain Sui proof reference (PostgreSQL row)."""

    proof_id: str
    sui_tx_hash: str = ""
    memory_id: str = ""
    content_hash: str = ""
    created_at: str = ""


# ---------------------------------------------------------------------------
# MCP tool response models
# ---------------------------------------------------------------------------

class StoreMemoryResult(BaseModel):
    """Response from the store_memory tool."""

    memory_id: str
    walrus_blob_id: str = ""
    namespace: str = ""
    status: str = "stored"


class SearchMemoryResult(BaseModel):
    """A single memory returned by search_memory."""

    memory_id: str
    content: str
    namespace: str = ""
    owner: str = ""
    tags: list[str] = Field(default_factory=list)
    relevance_score: float = 0.0
    metadata: dict[str, Any] = Field(default_factory=dict)
    walrus_blob_id: str = ""
    created_at: str = ""


class UpdateMemoryResult(BaseModel):
    """Response from the update_memory tool."""

    memory_id: str
    walrus_blob_id: str = ""
    status: str = "updated"


class DeleteMemoryResult(BaseModel):
    """Response from the delete_memory tool."""

    status: str = "deleted"


class VerifyResult(BaseModel):
    """Response from the verify_memory tool."""

    memory_id: str
    verified: bool
    content_hash_match: bool = False
    hmac_match: bool = False
    walrus_blob_exists: bool = False
    sui_proof_exists: bool = False
    walrus_blob_id: str = ""
    sui_tx_hash: str = ""
    algorithm: str = "sha256+hmac-sha256"
    message: str = ""


class StoreArtifactResult(BaseModel):
    """Response from the store_artifact tool."""

    artifact_id: str
    walrus_blob_id: str = ""
    status: str = "stored"


class GetArtifactResult(BaseModel):
    """Response from the get_artifact tool."""

    artifact_id: str
    content: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    walrus_blob_id: str = ""
    owner: str = ""
    filename: str = ""
    content_type: str = ""


class ListMemoriesResult(BaseModel):
    """Response from the list_memories tool."""

    memories: list[dict[str, Any]] = Field(default_factory=list)
    total: int = 0


class ListArtifactsResult(BaseModel):
    """Response from the list_artifacts tool."""

    artifacts: list[dict[str, Any]] = Field(default_factory=list)
    total: int = 0


class GraphNode(BaseModel):
    """A node in the memory graph."""

    memory_id: str
    namespace: str
    owner: str
    tags: list[str]


class GraphEdge(BaseModel):
    """An edge in the memory graph."""

    source_id: str
    target_id: str
    type: str


class ShowGraphResult(BaseModel):
    """Response from the show_graph tool."""

    nodes: list[GraphNode] = Field(default_factory=list)
    edges: list[GraphEdge] = Field(default_factory=list)


class InspectResult(BaseModel):
    """Response from the inspect_memory tool."""

    memory_id: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    relations: list[GraphEdge] = Field(default_factory=list)

