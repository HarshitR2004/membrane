"""Tests for the Artifact Manager — artifact lifecycle with Walrus."""

from __future__ import annotations

import pytest

from membrane.artifact_manager import ArtifactManager


@pytest.fixture()
def artifact_manager(fake_walrus, settings):
    return ArtifactManager(fake_walrus, settings)


@pytest.mark.asyncio
async def test_store_and_get_artifact(artifact_manager, db):
    """Store an artifact and retrieve it."""
    result = await artifact_manager.store(
        db=db,
        content="A very large document body " * 100,
        filename="report.pdf",
        content_type="application/pdf",
        tags=["report", "q4"],
        metadata={"format": "text"},
    )
    assert result.status == "stored"
    assert result.artifact_id
    assert result.walrus_blob_id

    got = await artifact_manager.get(db, result.artifact_id)
    assert got is not None
    assert "A very large document body" in got["content"]
    assert got["filename"] == "report.pdf"
    assert got["content_type"] == "application/pdf"
    assert got["metadata"]["format"] == "text"


@pytest.mark.asyncio
async def test_get_nonexistent_artifact(artifact_manager, db):
    """Getting a non-existent artifact returns None."""
    got = await artifact_manager.get(db, "does-not-exist")
    assert got is None


@pytest.mark.asyncio
async def test_list_artifacts(artifact_manager, db):
    """List artifacts with owner filtering."""
    await artifact_manager.store(
        db=db, content="doc1", owner="alice"
    )
    await artifact_manager.store(
        db=db, content="doc2", owner="bob"
    )
    await artifact_manager.store(
        db=db, content="doc3", owner="alice"
    )

    all_arts = await artifact_manager.list_artifacts(db)
    assert len(all_arts) == 3

    alice_arts = await artifact_manager.list_artifacts(db, owner="alice")
    assert len(alice_arts) == 2

    bob_arts = await artifact_manager.list_artifacts(db, owner="bob")
    assert len(bob_arts) == 1


@pytest.mark.asyncio
async def test_no_content_in_sqlite(artifact_manager, db):
    """Verify that no content is stored in the SQLite artifacts table."""
    result = await artifact_manager.store(
        db=db, content="this should not be in sqlite"
    )

    cursor = await db.execute(
        "SELECT * FROM artifacts WHERE artifact_id = ?", (result.artifact_id,)
    )
    row = await cursor.fetchone()
    assert row is not None

    column_names = [desc[0] for desc in cursor.description]
    assert "content" not in column_names
