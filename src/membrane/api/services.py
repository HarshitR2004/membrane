"""Business logic for Membrane Control Plane APIs."""

import hashlib
import secrets
import uuid
from datetime import datetime, timezone

import aiosqlite

from membrane.users import User, create_user, get_user_by_wallet, claim_membrane_id
from membrane.scoped_managers import ScopedMemoryManager, ScopedArtifactManager

def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

class AuthService:
    @staticmethod
    async def connect_wallet(db: aiosqlite.Connection, wallet: str, signature: str, message: str) -> tuple[User, bool]:
        """Connect wallet, auto-provisioning user if they don't exist."""
        # For hackathon: verify_signature is mocked
        # if not verify_signature(wallet, message, signature):
        #     raise ValueError("Invalid signature")

        user = await get_user_by_wallet(db, wallet)
        first_login = False
        if not user:
            user = await create_user(
                db=db,
                wallet_address=wallet,
                username=None,
                namespace=wallet,
            )
            first_login = True
        
        return user, first_login

class UserService:
    @staticmethod
    async def claim_id(db: aiosqlite.Connection, wallet: str, username: str) -> User:
        """Claim a Membrane ID (username)."""
        # Ensure username isn't taken
        cursor = await db.execute("SELECT id FROM users WHERE username = ?", (username,))
        if await cursor.fetchone():
            raise ValueError(f"Username '{username}' is already taken.")
        
        user = await claim_membrane_id(db, wallet, username)
        if not user:
            raise ValueError(f"User with wallet '{wallet}' not found.")
        return user

class APIKeyService:
    @staticmethod
    def _hash_key(key: str) -> str:
        return hashlib.sha256(key.encode()).hexdigest()

    @staticmethod
    def _generate_plaintext_key() -> str:
        return "mem_sk_" + secrets.token_urlsafe(32)

    @classmethod
    async def generate_key(cls, db: aiosqlite.Connection, user_id: str, name: str) -> tuple[str, str]:
        """Generate a new API key and return (plaintext_key, created_at)."""
        plaintext = cls._generate_plaintext_key()
        key_hash = cls._hash_key(plaintext)
        key_id = str(uuid.uuid4())
        now = _now_iso()

        await db.execute(
            """
            INSERT INTO api_keys (id, user_id, name, key_hash, key_value, created_at, last_used, is_active)
            VALUES (?, ?, ?, ?, ?, ?, ?, 1)
            """,
            (key_id, user_id, name, key_hash, plaintext, now, now)
        )
        await db.commit()
        return plaintext, now

    @classmethod
    async def list_keys(cls, db: aiosqlite.Connection, user_id: str) -> list[dict]:
        """List all API keys for a user."""
        cursor = await db.execute(
            "SELECT id, name, key_value, created_at, last_used, is_active FROM api_keys WHERE user_id = ? ORDER BY created_at DESC",
            (user_id,)
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]

    @classmethod
    async def rotate_key(cls, db: aiosqlite.Connection, user_id: str, key_id: str) -> str:
        """Deactivate an old key and generate a new one."""
        cursor = await db.execute("SELECT name FROM api_keys WHERE id = ? AND user_id = ?", (key_id, user_id))
        row = await cursor.fetchone()
        if not row:
            raise ValueError("Key not found.")
        name = row[0]

        await db.execute("UPDATE api_keys SET is_active = 0 WHERE id = ?", (key_id,))
        plaintext, _ = await cls.generate_key(db, user_id, name)
        return plaintext

    @classmethod
    async def delete_key(cls, db: aiosqlite.Connection, user_id: str, key_id: str) -> None:
        """Permanently delete a key."""
        cursor = await db.execute("DELETE FROM api_keys WHERE id = ? AND user_id = ?", (key_id, user_id))
        if cursor.rowcount == 0:
            raise ValueError("Key not found or not owned by user.")
        await db.commit()

    @classmethod
    async def verify_key(cls, db: aiosqlite.Connection, plaintext: str) -> str | None:
        """Verify key and return user_id if valid."""
        key_hash = cls._hash_key(plaintext)
        cursor = await db.execute("SELECT user_id, id FROM api_keys WHERE key_hash = ? AND is_active = 1", (key_hash,))
        row = await cursor.fetchone()
        if row:
            now = _now_iso()
            await db.execute("UPDATE api_keys SET last_used = ? WHERE id = ?", (now, row[1]))
            await db.commit()
            return row[0]
        return None

class StatsService:
    @staticmethod
    async def get_stats(db: aiosqlite.Connection, memory_manager: ScopedMemoryManager, artifact_manager: ScopedArtifactManager) -> dict:
        """Get dashboard stats using scoped managers."""
        memories = await memory_manager.list_memories(db)
        artifacts = await artifact_manager.list_artifacts(db)
        
        mem_count = len(memories)
        art_count = len(artifacts)
        
        # Simple count for workflows and shared
        workflows = sum(1 for a in artifacts if a.get("type") == "workflow")
        # Let's consider shared as anything with allowed_agents or allowed_users > 0 or visibility != 'private'
        shared_mems = sum(1 for m in memories if m.get("visibility") != "private" or m.get("allowed_users") or m.get("allowed_agents"))
        shared_arts = sum(1 for a in artifacts if a.get("visibility") != "private" or a.get("allowed_users") or a.get("allowed_agents"))
        
        return {
            "memories": mem_count,
            "artifacts": art_count,
            "workflows": workflows,
            "shared": shared_mems + shared_arts
        }

import os

class ConfigService:
    @staticmethod
    def universal_config(user: User) -> dict:
        identifier = user.username or user.wallet_address
        # Render automatically provides RENDER_EXTERNAL_URL. 
        # We fall back to MEMBRANE_EXTERNAL_URL or localhost.
        base_url = os.getenv("RENDER_EXTERNAL_URL") or os.getenv("MEMBRANE_EXTERNAL_URL", "http://localhost:8000")
        return {
            "mcpServers": {
                f"membrane-{identifier}": {
                    "url": f"{base_url}/mcp/{identifier}/sse",
                    "headers": {
                        "Authorization": "Bearer <YOUR_API_KEY>"
                    }
                }
            }
        }
