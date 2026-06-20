"""User management and CRUD operations."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

import asyncpg
from pydantic import BaseModel


class User(BaseModel):
    """A user in the multi-tenant Membrane system."""
    id: str
    username: str | None
    wallet_address: str
    namespace: str
    created_at: str
    last_active: str


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


async def create_user(
    db: asyncpg.Connection,
    wallet_address: str,
    username: str | None = None,
    namespace: str | None = None,
) -> User:
    """Create a new user."""
    user_id = str(uuid.uuid4())
    now = _now_iso()
    ns = namespace or username or wallet_address

    await db.execute(
        """
        INSERT INTO users (id, username, wallet_address, namespace, created_at, last_active)
        VALUES ($1, $2, $3, $4, $5, $6)
        """,
        user_id, username, wallet_address, ns, now, now
    )

    return User(
        id=user_id,
        username=username,
        wallet_address=wallet_address,
        namespace=ns,
        created_at=now,
        last_active=now,
    )


async def get_user(
    db: asyncpg.Connection,
    username: str,
) -> User | None:
    """Get a user by username or wallet address."""
    row = await db.fetchrow(
        "SELECT * FROM users WHERE username = $1 OR wallet_address = $2",
        username, username
    )
    if not row:
        return None
    return User(**dict(row))


async def get_user_by_wallet(
    db: asyncpg.Connection,
    wallet_address: str,
) -> User | None:
    """Get a user by wallet address."""
    row = await db.fetchrow(
        "SELECT * FROM users WHERE wallet_address = $1",
        wallet_address
    )
    if not row:
        return None
    return User(**dict(row))


async def list_users(
    db: asyncpg.Connection,
) -> list[User]:
    """List all users."""
    rows = await db.fetch("SELECT * FROM users ORDER BY created_at DESC")
    return [User(**dict(row)) for row in rows]


async def update_last_active(
    db: asyncpg.Connection,
    username: str,
) -> None:
    """Update a user's last_active timestamp by id."""
    now = _now_iso()
    await db.execute(
        "UPDATE users SET last_active = $1 WHERE id = $2 OR username = $3 OR wallet_address = $4",
        now, username, username, username
    )


async def claim_membrane_id(
    db: asyncpg.Connection,
    wallet_address: str,
    username: str,
) -> User | None:
    """Claim a human-readable username and set it as namespace."""
    await db.execute(
        "UPDATE users SET username = $1, namespace = $2 WHERE wallet_address = $3",
        username, username, wallet_address
    )
    return await get_user_by_wallet(db, wallet_address)
