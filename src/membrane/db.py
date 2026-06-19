"""SQLite database initialization and connection management.

The local database stores **metadata only** — no memory content or artifact
bodies.  All content lives in Walrus.  SQLite serves as a fast index for
namespace/owner/tag filtering and embedding-based reranking.
"""

from __future__ import annotations

import aiosqlite

# ---------------------------------------------------------------------------
# Schema DDL — metadata-only tables
# ---------------------------------------------------------------------------

_SCHEMA = """
CREATE TABLE IF NOT EXISTS memories (
    memory_id       TEXT PRIMARY KEY,
    namespace       TEXT NOT NULL DEFAULT 'default',
    owner           TEXT NOT NULL DEFAULT '',
    visibility      TEXT NOT NULL DEFAULT 'private',
    allowed_agents  TEXT NOT NULL DEFAULT '[]',
    allowed_users   TEXT NOT NULL DEFAULT '[]',
    tags            TEXT NOT NULL DEFAULT '[]',
    timestamp       TEXT NOT NULL,
    walrus_blob_id  TEXT NOT NULL,
    content_hash    TEXT NOT NULL,
    proof_id        TEXT,
    embedding       BLOB
);

CREATE TABLE IF NOT EXISTS artifacts (
    artifact_id     TEXT PRIMARY KEY,
    walrus_blob_id  TEXT NOT NULL,
    owner           TEXT NOT NULL DEFAULT '',
    visibility      TEXT NOT NULL DEFAULT 'private',
    allowed_agents  TEXT NOT NULL DEFAULT '[]',
    allowed_users   TEXT NOT NULL DEFAULT '[]',
    type            TEXT NOT NULL DEFAULT 'artifact',
    filename        TEXT NOT NULL DEFAULT '',
    content_type    TEXT NOT NULL DEFAULT '',
    tags            TEXT NOT NULL DEFAULT '[]',
    timestamp       TEXT NOT NULL,
    content_hash    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS proofs (
    proof_id        TEXT PRIMARY KEY,
    sui_tx_hash     TEXT NOT NULL,
    memory_id       TEXT NOT NULL,
    content_hash    TEXT NOT NULL,
    created_at      TEXT NOT NULL,
    FOREIGN KEY (memory_id) REFERENCES memories(memory_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS memory_relations (
    source_id       TEXT NOT NULL,
    target_id       TEXT NOT NULL,
    relation_type   TEXT NOT NULL,
    FOREIGN KEY (source_id) REFERENCES memories(memory_id) ON DELETE CASCADE,
    FOREIGN KEY (target_id) REFERENCES memories(memory_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS users (
    id              TEXT PRIMARY KEY,
    username        TEXT UNIQUE,
    wallet_address  TEXT UNIQUE NOT NULL,
    namespace       TEXT NOT NULL,
    created_at      TEXT NOT NULL,
    last_active     TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS api_keys (
    id              TEXT PRIMARY KEY,
    user_id         TEXT NOT NULL,
    name            TEXT NOT NULL,
    key_hash        TEXT NOT NULL,
    key_value       TEXT,
    created_at      TEXT NOT NULL,
    last_used       TEXT NOT NULL,
    is_active       BOOLEAN NOT NULL DEFAULT 1,
    FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_memories_namespace ON memories(namespace);
CREATE INDEX IF NOT EXISTS idx_memories_owner ON memories(owner);
CREATE INDEX IF NOT EXISTS idx_artifacts_owner ON artifacts(owner);
CREATE INDEX IF NOT EXISTS idx_proofs_memory_id ON proofs(memory_id);
CREATE INDEX IF NOT EXISTS idx_memory_relations_source ON memory_relations(source_id);
CREATE INDEX IF NOT EXISTS idx_memory_relations_target ON memory_relations(target_id);
CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);
CREATE INDEX IF NOT EXISTS idx_users_wallet ON users(wallet_address);
CREATE INDEX IF NOT EXISTS idx_api_keys_user ON api_keys(user_id);
"""

async def _migrate_tables(db: aiosqlite.Connection) -> None:
    """Check for and add missing columns to existing tables for backwards compatibility."""
    # Check memories table columns
    cursor = await db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='memories'")
    if await cursor.fetchone():
        cursor = await db.execute("PRAGMA table_info(memories)")
        columns = [row[1] for row in await cursor.fetchall()]
        if "namespace" not in columns:
            await db.execute("ALTER TABLE memories ADD COLUMN namespace TEXT NOT NULL DEFAULT 'default'")
        if "owner" not in columns:
            await db.execute("ALTER TABLE memories ADD COLUMN owner TEXT NOT NULL DEFAULT ''")
        if "visibility" not in columns:
            await db.execute("ALTER TABLE memories ADD COLUMN visibility TEXT NOT NULL DEFAULT 'private'")
        if "allowed_agents" not in columns:
            await db.execute("ALTER TABLE memories ADD COLUMN allowed_agents TEXT NOT NULL DEFAULT '[]'")
        if "allowed_users" not in columns:
            await db.execute("ALTER TABLE memories ADD COLUMN allowed_users TEXT NOT NULL DEFAULT '[]'")
        if "tags" not in columns:
            await db.execute("ALTER TABLE memories ADD COLUMN tags TEXT NOT NULL DEFAULT '[]'")
        if "timestamp" not in columns:
            await db.execute("ALTER TABLE memories ADD COLUMN timestamp TEXT NOT NULL DEFAULT ''")
        if "walrus_blob_id" not in columns:
            await db.execute("ALTER TABLE memories ADD COLUMN walrus_blob_id TEXT NOT NULL DEFAULT ''")
        if "content_hash" not in columns:
            await db.execute("ALTER TABLE memories ADD COLUMN content_hash TEXT NOT NULL DEFAULT ''")
        if "proof_id" not in columns:
            await db.execute("ALTER TABLE memories ADD COLUMN proof_id TEXT")
        if "embedding" not in columns:
            await db.execute("ALTER TABLE memories ADD COLUMN embedding BLOB")

    # Check artifacts table columns
    cursor = await db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='artifacts'")
    if await cursor.fetchone():
        cursor = await db.execute("PRAGMA table_info(artifacts)")
        columns = [row[1] for row in await cursor.fetchall()]
        if "walrus_blob_id" not in columns:
            await db.execute("ALTER TABLE artifacts ADD COLUMN walrus_blob_id TEXT NOT NULL DEFAULT ''")
        if "owner" not in columns:
            await db.execute("ALTER TABLE artifacts ADD COLUMN owner TEXT NOT NULL DEFAULT ''")
        if "visibility" not in columns:
            await db.execute("ALTER TABLE artifacts ADD COLUMN visibility TEXT NOT NULL DEFAULT 'private'")
        if "allowed_agents" not in columns:
            await db.execute("ALTER TABLE artifacts ADD COLUMN allowed_agents TEXT NOT NULL DEFAULT '[]'")
        if "allowed_users" not in columns:
            await db.execute("ALTER TABLE artifacts ADD COLUMN allowed_users TEXT NOT NULL DEFAULT '[]'")
        if "type" not in columns:
            await db.execute("ALTER TABLE artifacts ADD COLUMN type TEXT NOT NULL DEFAULT 'artifact'")
        if "filename" not in columns:
            await db.execute("ALTER TABLE artifacts ADD COLUMN filename TEXT NOT NULL DEFAULT ''")
        if "content_type" not in columns:
            await db.execute("ALTER TABLE artifacts ADD COLUMN content_type TEXT NOT NULL DEFAULT ''")
        if "tags" not in columns:
            await db.execute("ALTER TABLE artifacts ADD COLUMN tags TEXT NOT NULL DEFAULT '[]'")
        if "timestamp" not in columns:
            await db.execute("ALTER TABLE artifacts ADD COLUMN timestamp TEXT NOT NULL DEFAULT ''")
        if "content_hash" not in columns:
            await db.execute("ALTER TABLE artifacts ADD COLUMN content_hash TEXT NOT NULL DEFAULT ''")

    # Check proofs table columns
    cursor = await db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='proofs'")
    if await cursor.fetchone():
        cursor = await db.execute("PRAGMA table_info(proofs)")
        columns = [row[1] for row in await cursor.fetchall()]
        if "sui_tx_hash" not in columns:
            await db.execute("ALTER TABLE proofs ADD COLUMN sui_tx_hash TEXT NOT NULL DEFAULT ''")
        if "memory_id" not in columns:
            await db.execute("ALTER TABLE proofs ADD COLUMN memory_id TEXT NOT NULL DEFAULT ''")
        if "content_hash" not in columns:
            await db.execute("ALTER TABLE proofs ADD COLUMN content_hash TEXT NOT NULL DEFAULT ''")
        if "created_at" not in columns:
            await db.execute("ALTER TABLE proofs ADD COLUMN created_at TEXT NOT NULL DEFAULT ''")

    # Check users table for migration (making username nullable and wallet_address not null)
    cursor = await db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='users'")
    if await cursor.fetchone():
        cursor = await db.execute("PRAGMA table_info(users)")
        columns = await cursor.fetchall()
        for col in columns:
            if col[1] == "username" and col[3] == 1:
                # username is NOT NULL, need to migrate
                await db.execute("ALTER TABLE users RENAME TO users_old")
                await db.executescript('''
                    CREATE TABLE users (
                        id              TEXT PRIMARY KEY,
                        username        TEXT UNIQUE,
                        wallet_address  TEXT UNIQUE NOT NULL,
                        namespace       TEXT NOT NULL,
                        created_at      TEXT NOT NULL,
                        last_active     TEXT NOT NULL
                    );
                ''')
                # Coalesce wallet_address to id if it's null for existing records to satisfy NOT NULL
                await db.execute("INSERT INTO users SELECT id, username, coalesce(wallet_address, id), namespace, created_at, last_active FROM users_old")
                await db.execute("DROP TABLE users_old")
                # Recreate indexes
                await db.execute("CREATE INDEX IF NOT EXISTS idx_users_username ON users(username)")
                await db.execute("CREATE INDEX IF NOT EXISTS idx_users_wallet ON users(wallet_address)")
                break

    # Check api_keys table columns
    cursor = await db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='api_keys'")
    if await cursor.fetchone():
        cursor = await db.execute("PRAGMA table_info(api_keys)")
        columns = [row[1] for row in await cursor.fetchall()]
        if "key_value" not in columns:
            await db.execute("ALTER TABLE api_keys ADD COLUMN key_value TEXT")


async def init_db(db_path: str) -> None:
    """Create database tables if they do not already exist."""
    async with aiosqlite.connect(db_path) as db:
        await _migrate_tables(db)
        await db.executescript(_SCHEMA)
        await db.commit()


async def init_db_conn(db: aiosqlite.Connection) -> None:
    """Create database tables on an already-open connection.

    Useful for in-memory databases in tests where each ``connect(':memory:')``
    produces a separate, empty database.
    """
    await _migrate_tables(db)
    await db.executescript(_SCHEMA)
    await db.commit()


async def get_db(db_path: str) -> aiosqlite.Connection:
    """Open and return an async SQLite connection.

    The caller is responsible for closing the connection.
    """
    db = await aiosqlite.connect(db_path)
    db.row_factory = aiosqlite.Row
    # Enable foreign key enforcement
    await db.execute("PRAGMA foreign_keys = ON")
    return db
