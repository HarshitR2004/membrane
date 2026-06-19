"""FastAPI routers for Membrane Control Plane."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
import aiosqlite

from membrane.users import User
from membrane.api.schemas import (
    ConnectRequest, ConnectResponse,
    ClaimIdRequest, ClaimIdResponse,
    GenerateKeyRequest, GenerateKeyResponse,
    APIKeyItem,
    RotateKeyRequest,
    RotateKeyResponse,
    DeleteKeyRequest,
    DeleteKeyResponse,
    ProfileResponse,
    StatsResponse,
    MemoriesResponse,
    ArtifactsResponse,
    UniversalConfigResponse,
    StatusResponse,
)
from membrane.api.services import AuthService, UserService, APIKeyService, StatsService, ConfigService
from membrane.api.middleware import get_db_connection, get_current_user

router = APIRouter()

@router.post("/auth/connect", response_model=ConnectResponse)
async def connect_wallet(
    req: ConnectRequest,
    db: Annotated[aiosqlite.Connection, Depends(get_db_connection)]
):
    try:
        user, first_login = await AuthService.connect_wallet(db, req.wallet, req.signature, req.message)
        return ConnectResponse(
            user_id=user.id,
            wallet=user.wallet_address,
            username=user.username,
            namespace=user.namespace,
            first_login=first_login
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/profile/claim-id", response_model=ClaimIdResponse)
async def claim_membrane_id(
    req: ClaimIdRequest,
    db: Annotated[aiosqlite.Connection, Depends(get_db_connection)]
):
    try:
        user = await UserService.claim_id(db, req.wallet, req.username)
        return ClaimIdResponse(
            username=user.username,
            namespace=user.namespace
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/keys", response_model=GenerateKeyResponse)
async def generate_key(
    req: GenerateKeyRequest,
    db: Annotated[aiosqlite.Connection, Depends(get_db_connection)]
):
    from membrane.users import get_user_by_wallet
    user = await get_user_by_wallet(db, req.wallet)
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")
    
    plaintext, created_at = await APIKeyService.generate_key(db, user.id, req.name)
    return GenerateKeyResponse(key=plaintext, created_at=created_at)

@router.get("/keys", response_model=list[APIKeyItem])
async def list_keys(
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[aiosqlite.Connection, Depends(get_db_connection)]
):
    return await APIKeyService.list_keys(db, user.id)

@router.post("/keys/rotate", response_model=RotateKeyResponse)
async def rotate_key(
    req: RotateKeyRequest,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[aiosqlite.Connection, Depends(get_db_connection)]
):
    # Verify wallet belongs to user
    if user.wallet_address != req.wallet:
        raise HTTPException(status_code=403, detail="Wallet mismatch")
    
    try:
        plaintext = await APIKeyService.rotate_key(db, user.id, req.key_id)
        return RotateKeyResponse(key=plaintext)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

@router.post("/keys/delete", response_model=DeleteKeyResponse)
async def delete_key(
    req: DeleteKeyRequest,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[aiosqlite.Connection, Depends(get_db_connection)]
):
    # Verify wallet belongs to user
    if user.wallet_address != req.wallet:
        raise HTTPException(status_code=403, detail="Wallet mismatch")
    
    try:
        await APIKeyService.delete_key(db, user.id, req.key_id)
        return DeleteKeyResponse(success=True)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

@router.get("/profile", response_model=ProfileResponse)
async def get_profile(user: Annotated[User, Depends(get_current_user)]):
    return ProfileResponse(
        wallet=user.wallet_address,
        username=user.username,
        namespace=user.namespace,
        created_at=user.created_at
    )

@router.get("/stats", response_model=StatsResponse)
async def get_stats(
    request: Request,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[aiosqlite.Connection, Depends(get_db_connection)]
):
    from membrane.user_context import build_user_context
    from membrane.scoped_managers import ScopedMemoryManager, ScopedArtifactManager
    
    context = build_user_context(user)
    memory_manager = ScopedMemoryManager(request.app.state.memory_manager, context)
    artifact_manager = ScopedArtifactManager(request.app.state.artifact_manager, context)
    
    stats = await StatsService.get_stats(db, memory_manager, artifact_manager)
    return StatsResponse(**stats)

@router.get("/memories", response_model=MemoriesResponse)
async def get_memories(
    request: Request,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[aiosqlite.Connection, Depends(get_db_connection)],
    limit: int = 50,
    offset: int = 0
):
    from membrane.user_context import build_user_context
    from membrane.scoped_managers import ScopedMemoryManager
    
    context = build_user_context(user)
    memory_manager = ScopedMemoryManager(request.app.state.memory_manager, context)
    
    # Passing dummy query, our list_memories doesn't officially take limit/offset yet, 
    # but we can call it directly
    memories = await memory_manager.list_memories(db)
    items = memories
    total = len(items)
    return MemoriesResponse(items=items[offset:offset+limit], total=total)

@router.get("/artifacts", response_model=ArtifactsResponse)
async def get_artifacts(
    request: Request,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[aiosqlite.Connection, Depends(get_db_connection)],
    limit: int = 50,
    offset: int = 0
):
    from membrane.user_context import build_user_context
    from membrane.scoped_managers import ScopedArtifactManager
    
    context = build_user_context(user)
    artifact_manager = ScopedArtifactManager(request.app.state.artifact_manager, context)
    
    artifacts = await artifact_manager.list_artifacts(db)
    items = artifacts
    total = len(items)
    return ArtifactsResponse(items=items[offset:offset+limit], total=total)

@router.get("/config/universal", response_model=UniversalConfigResponse)
async def get_universal_config(user: Annotated[User, Depends(get_current_user)]):
    return UniversalConfigResponse(**ConfigService.universal_config(user))

@router.get("/status", response_model=StatusResponse)
async def get_status(
    request: Request,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[aiosqlite.Connection, Depends(get_db_connection)]
):
    # Check Walrus & Sui
    walrus = getattr(request.app.state, "walrus", None)
    sui = getattr(request.app.state, "sui", None)
    retrieval = getattr(request.app.state, "retrieval_engine", None)
    
    from membrane.user_context import build_user_context
    from membrane.scoped_managers import ScopedMemoryManager
    context = build_user_context(user)
    memory_manager = ScopedMemoryManager(request.app.state.memory_manager, context)
    memories = await memory_manager.list_memories(db)
    
    return StatusResponse(
        online=True,
        walrus=walrus is not None,
        sui=sui is not None,
        retrieval=retrieval is not None,
        memories=len(memories)
    )
