"""Pydantic schemas for Membrane Control Plane APIs."""

from typing import Any
from pydantic import BaseModel, Field

class ConnectRequest(BaseModel):
    wallet: str
    signature: str = ""
    message: str = "Login to Membrane"

class ConnectResponse(BaseModel):
    user_id: str
    wallet: str
    username: str | None
    namespace: str
    first_login: bool

class ClaimIdRequest(BaseModel):
    wallet: str
    username: str = Field(pattern=r"^[a-z0-9_-]{3,30}$")

class ClaimIdResponse(BaseModel):
    username: str
    namespace: str

class GenerateKeyRequest(BaseModel):
    wallet: str
    name: str

class GenerateKeyResponse(BaseModel):
    key: str
    created_at: str

class APIKeyItem(BaseModel):
    id: str
    name: str
    key_value: str | None
    created_at: str
    last_used: str
    is_active: bool

class RotateKeyRequest(BaseModel):
    wallet: str
    key_id: str

class RotateKeyResponse(BaseModel):
    key: str

class DeleteKeyRequest(BaseModel):
    wallet: str
    key_id: str

class DeleteKeyResponse(BaseModel):
    success: bool

class ProfileResponse(BaseModel):
    wallet: str
    username: str | None
    namespace: str
    created_at: str

class StatsResponse(BaseModel):
    memories: int
    artifacts: int
    workflows: int
    shared: int

class MemoriesResponse(BaseModel):
    items: list[dict[str, Any]]
    total: int

class ArtifactsResponse(BaseModel):
    items: list[dict[str, Any]]
    total: int

class UniversalConfigResponse(BaseModel):
    mcpServers: dict[str, Any]

class StatusResponse(BaseModel):
    online: bool
    walrus: bool
    sui: bool
    retrieval: bool
    memories: int
