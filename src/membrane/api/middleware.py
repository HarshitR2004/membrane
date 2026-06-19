"""Middleware and dependencies for Membrane Control Plane APIs."""

from typing import Annotated

from fastapi import Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import aiosqlite

from membrane.db import get_db
from membrane.api.services import APIKeyService
from membrane.users import User, update_last_active

security = HTTPBearer()

async def get_db_connection(request: Request) -> aiosqlite.Connection:
    """Dependency to get DB connection from app state."""
    db_path = request.app.state.settings.db_path
    db = await get_db(db_path)
    try:
        yield db
    finally:
        await db.close()

async def get_current_user(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(security)],
    db: Annotated[aiosqlite.Connection, Depends(get_db_connection)]
) -> User:
    """Dependency to resolve User from API key."""
    token = credentials.credentials
    if not token.startswith("mem_sk_"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API Key format",
        )
    
    user_id = await APIKeyService.verify_key(db, token)
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or inactive API Key",
        )
    
    cursor = await db.execute("SELECT * FROM users WHERE id = ?", (user_id,))
    row = await cursor.fetchone()
    if not row:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )
    
    user = User(**dict(row))
    await update_last_active(db, user.username or user.wallet_address)
    
    # Attach user to request state
    request.state.user = user
    return user
