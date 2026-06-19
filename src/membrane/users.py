"""User management and CRUD operations."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

import aiosqlite
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
    db: aiosqlite.Connection,
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
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (user_id, username, wallet_address, ns, now, now)
    )
    await db.commit()

    return User(
        id=user_id,
        username=username,
        wallet_address=wallet_address,
        namespace=ns,
        created_at=now,
        last_active=now,
    )


async def get_user(
    db: aiosqlite.Connection,
    username: str,
) -> User | None:
    """Get a user by username or wallet address."""
    cursor = await db.execute(
        "SELECT * FROM users WHERE username = ? OR wallet_address = ?",
        (username, username)
    )
    row = await cursor.fetchone()
    if not row:
        return None
    return User(**dict(row))


async def get_user_by_wallet(
    db: aiosqlite.Connection,
    wallet_address: str,
) -> User | None:
    """Get a user by wallet address."""
    cursor = await db.execute(
        "SELECT * FROM users WHERE wallet_address = ?",
        (wallet_address,)
    )
    row = await cursor.fetchone()
    if not row:
        return None
    return User(**dict(row))


async def list_users(
    db: aiosqlite.Connection,
) -> list[User]:
    """List all users."""
    cursor = await db.execute("SELECT * FROM users ORDER BY created_at DESC")
    rows = await cursor.fetchall()
    return [User(**dict(row)) for row in rows]


async def update_last_active(
    db: aiosqlite.Connection,
    username: str,
) -> None:
    """Update a user's last_active timestamp by id."""
    now = _now_iso()
    await db.execute(
        "UPDATE users SET last_active = ? WHERE id = ? OR username = ? OR wallet_address = ?",
        (now, username, username, username)
    )
    await db.commit()

async def claim_membrane_id(
    db: aiosqlite.Connection,
    wallet_address: str,
    username: str,
) -> User | None:
    """Claim a human-readable username and set it as namespace."""
    await db.execute(
        "UPDATE users SET username = ?, namespace = ? WHERE wallet_address = ?",
        (username, username, wallet_address)
    )
    await db.commit()
    return await get_user_by_wallet(db, wallet_address)
