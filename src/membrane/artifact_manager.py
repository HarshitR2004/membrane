"""Artifact Manager — orchestrates artifact lifecycle with Walrus.

Stores artifact content (PDFs, reports, datasets, logs, images, etc.)
in Walrus and maintains lightweight metadata records in SQLite.  This
replaces the old ``artifacts.py`` which kept content in the database.
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any

import aiosqlite

from membrane.config import MembraneSettings
from membrane.models import ArtifactPayload, StoreArtifactResult
from membrane.security import generate_content_hash
from membrane.walrus_client import WalrusClient, WalrusError

logger = logging.getLogger(__name__)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class ArtifactManager:
    """Manages artifact lifecycle with Walrus as canonical storage.

    Write flow:
      1. Compute SHA-256 hash of content
      2. Build ``ArtifactPayload`` JSON
      3. Upload to Walrus → ``blob_id``
      4. Save metadata in SQLite (no content)

    Read flow:
      1. Look up metadata in SQLite
      2. Fetch blob from Walrus
      3. Parse and return artifact content
    """

    def __init__(
        self,
        walrus: WalrusClient,
        settings: MembraneSettings,
    ) -> None:
        self._walrus = walrus
        self._settings = settings

    # ------------------------------------------------------------------
    # Store
    # ------------------------------------------------------------------

    async def store(
        self,
        db: aiosqlite.Connection,
        content: str,
        owner: str | None = None,
        type: str = "artifact",
        visibility: str = "private",
        allowed_agents: list[str] | None = None,
        allowed_users: list[str] | None = None,
        filename: str = "",
        content_type: str = "",
        tags: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> StoreArtifactResult:
        """Store a new artifact in Walrus with metadata in SQLite."""
        artifact_id = str(uuid.uuid4())
        now = _now_iso()
        own = owner or self._settings.default_owner
        tag_list = tags or []
        extra = metadata or {}
        allowed_agents_list = allowed_agents or []
        allowed_users_list = allowed_users or []

        # 1. Content hash
        content_hash = generate_content_hash(content)

        # 2. Build payload
        payload = ArtifactPayload(
            artifact_id=artifact_id,
            owner=own,
            visibility=visibility,
            allowed_agents=allowed_agents_list,
            allowed_users=allowed_users_list,
            filename=filename,
            content_type=content_type,
            created_at=now,
            type=type,
            content=content,
            metadata=extra,
        )

        # 3. Upload to Walrus
        payload_bytes = payload.model_dump_json().encode("utf-8")
        walrus_result = await self._walrus.store_blob(payload_bytes)
        blob_id = walrus_result.blob_id

        # 4. Save metadata in SQLite
        await db.execute(
            """
            INSERT INTO artifacts
                (artifact_id, walrus_blob_id, owner, visibility, allowed_agents, allowed_users, type, filename,
                 content_type, tags, timestamp, content_hash)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                artifact_id, blob_id, own, visibility, json.dumps(allowed_agents_list), json.dumps(allowed_users_list), type, filename,
                content_type, json.dumps(tag_list), now, content_hash,
            ),
        )
        await db.commit()

        logger.info(
            "Artifact stored: id=%s blob=%s filename=%s",
            artifact_id, blob_id, filename,
        )

        return StoreArtifactResult(
            artifact_id=artifact_id,
            walrus_blob_id=blob_id,
            status="stored",
        )

    # ------------------------------------------------------------------
    # Get
    # ------------------------------------------------------------------

    async def get(
        self,
        db: aiosqlite.Connection,
        artifact_id: str,
    ) -> dict[str, Any] | None:
        """Retrieve an artifact by ID — fetches content from Walrus."""
        cursor = await db.execute(
            "SELECT * FROM artifacts WHERE artifact_id = ?", (artifact_id,)
        )
        row = await cursor.fetchone()
        if row is None:
            return None

        walrus_blob_id = row["walrus_blob_id"]

        # Fetch from Walrus
        try:
            blob_bytes = await self._walrus.get_blob(walrus_blob_id)
        except WalrusError as exc:
            logger.warning("Failed to fetch artifact from Walrus: %s", exc)
            return {
                "artifact_id": artifact_id,
                "error": f"Failed to fetch content from Walrus: {exc}",
                "walrus_blob_id": walrus_blob_id,
            }

        # Parse payload
        payload = json.loads(blob_bytes.decode("utf-8"))

        return {
            "artifact_id": artifact_id,
            "content": payload.get("content", ""),
            "metadata": payload.get("metadata", {}),
            "walrus_blob_id": walrus_blob_id,
            "owner": row["owner"],
            "filename": row["filename"],
            "content_type": row["content_type"],
            "created_at": payload.get("created_at", row["timestamp"]),
            "type": dict(row).get("type", "artifact"),
            "visibility": dict(row).get("visibility", "private"),
            "allowed_agents": json.loads(dict(row).get("allowed_agents", "[]")),
            "allowed_users": json.loads(dict(row).get("allowed_users", "[]")),
        }

    # ------------------------------------------------------------------
    # List
    # ------------------------------------------------------------------

    async def list_artifacts(
        self,
        db: aiosqlite.Connection,
        owner: str | None = None,
        type: str | None = None,
    ) -> list[dict[str, Any]]:
        """List artifact metadata records (without fetching Walrus content)."""
        query = "SELECT * FROM artifacts WHERE 1=1"
        params: list[str] = []

        if owner:
            query += " AND owner = ?"
            params.append(owner)
        if type:
            query += " AND type = ?"
            params.append(type)

        query += " ORDER BY timestamp DESC"

        cursor = await db.execute(query, params)
        rows = await cursor.fetchall()

        return [
            {
                "artifact_id": row["artifact_id"],
                "walrus_blob_id": row["walrus_blob_id"],
                "owner": row["owner"],
                "visibility": dict(row).get("visibility", "private"),
                "allowed_agents": json.loads(dict(row).get("allowed_agents", "[]")),
                "allowed_users": json.loads(dict(row).get("allowed_users", "[]")),
                "type": dict(row).get("type", "artifact"),
                "filename": row["filename"],
                "content_type": row["content_type"],
                "tags": json.loads(row["tags"]),
                "timestamp": row["timestamp"],
                "content_hash": row["content_hash"],
            }
            for row in rows
        ]
