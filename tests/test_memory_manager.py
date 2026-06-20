"""Tests for the Memory Manager — full memory lifecycle with Walrus."""

from __future__ import annotations

import json

import pytest

from membrane.memory_manager import MemoryManager
from tests.conftest import TEST_KEY, TEST_SECRET


@pytest.fixture()
def memory_manager(fake_walrus, fake_sui, settings):
    return MemoryManager(fake_walrus, fake_sui, settings)


@pytest.mark.asyncio
async def test_store_and_get(memory_manager, db):
    """Store a memory and retrieve it by ID."""
    result = await memory_manager.store(
        db=db,
        content="The capital of France is Paris.",
        namespace="geo",
        tags=["geography", "europe"],
        metadata={"source": "agent"},
    )
    assert result.status == "stored"
    assert result.memory_id
    assert result.walrus_blob_id
    assert result.namespace == "geo"

    got = await memory_manager.get(db, result.memory_id)
    assert got is not None
    assert got["content"] == "The capital of France is Paris."
    assert got["namespace"] == "geo"
    assert "geography" in got["tags"]


@pytest.mark.asyncio
async def test_store_encrypted(memory_manager, db):
    """Store an encrypted memory and verify decryption on get."""
    result = await memory_manager.store(
        db=db,
        content="Secret: the answer is 42",
        encrypt=True,
    )
    assert result.status == "stored"

    got = await memory_manager.get(db, result.memory_id)
    assert got is not None
    assert got["content"] == "Secret: the answer is 42"
    assert got["is_encrypted"] is True


@pytest.mark.asyncio
async def test_update_memory(memory_manager, db):
    """Update a memory's content and verify the change persists."""
    result = await memory_manager.store(db=db, content="v1")
    memory_id = result.memory_id

    update_result = await memory_manager.update(
        db=db, memory_id=memory_id, content="v2", tags=["updated"]
    )
    assert update_result["status"] == "updated"

    got = await memory_manager.get(db, memory_id)
    assert got["content"] == "v2"
    assert "updated" in got["tags"]


@pytest.mark.asyncio
async def test_update_nonexistent(memory_manager, db):
    """Updating a non-existent memory returns an error."""
    result = await memory_manager.update(
        db=db, memory_id="no-such-id", content="x"
    )
    assert "error" in result


@pytest.mark.asyncio
async def test_delete_memory(memory_manager, db):
    """Delete a memory and verify it's gone."""
    result = await memory_manager.store(db=db, content="to delete")
    memory_id = result.memory_id

    del_result = await memory_manager.delete(db=db, memory_id=memory_id)
    assert del_result["status"] == "deleted"

    got = await memory_manager.get(db, memory_id)
    assert got is None


@pytest.mark.asyncio
async def test_delete_nonexistent(memory_manager, db):
    """Deleting a non-existent memory returns an error."""
    result = await memory_manager.delete(db=db, memory_id="no-such-id")
    assert "error" in result


@pytest.mark.asyncio
async def test_list_memories(memory_manager, db):
    """List memories with namespace filtering."""
    await memory_manager.store(db=db, content="mem1", namespace="ns1")
    await memory_manager.store(db=db, content="mem2", namespace="ns2")
    await memory_manager.store(db=db, content="mem3", namespace="ns1")

    all_mems = await memory_manager.list_memories(db)
    assert len(all_mems) == 3

    ns1_mems = await memory_manager.list_memories(db, namespace="ns1")
    assert len(ns1_mems) == 2

    ns2_mems = await memory_manager.list_memories(db, namespace="ns2")
    assert len(ns2_mems) == 1


@pytest.mark.asyncio
async def test_store_with_sui_proof(db, fake_walrus, fake_sui, settings):
    """When Sui is enabled, store should record a proof."""
    mgr = MemoryManager(fake_walrus, fake_sui, settings)
    result = await mgr.store(db=db, content="proof this")

    # Check proof exists in the proofs table
    cursor = await db.execute(
        "SELECT * FROM proofs WHERE memory_id = ?", (result.memory_id,)
    )
    row = await cursor.fetchone()
    assert row is not None
    assert row["sui_tx_hash"]
    assert row["content_hash"]


@pytest.mark.asyncio
async def test_store_without_sui(db, fake_walrus, fake_sui_disabled, settings):
    """When Sui is disabled, store succeeds without a proof."""
    mgr = MemoryManager(fake_walrus, fake_sui_disabled, settings)
    result = await mgr.store(db=db, content="no proof needed")
    assert result.status == "stored"

    # No proof in proofs table
    cursor = await db.execute(
        "SELECT * FROM proofs WHERE memory_id = ?", (result.memory_id,)
    )
    row = await cursor.fetchone()
    assert row is None


@pytest.mark.asyncio
async def test_no_content_in_sqlite(memory_manager, db):
    """Verify that no content is stored in the PostgreSQL memories table."""
    result = await memory_manager.store(
        db=db, content="this should not be in sqlite"
    )

    cursor = await db.execute(
        "SELECT * FROM memories WHERE memory_id = ?", (result.memory_id,)
    )
    row = await cursor.fetchone()
    assert row is not None

    # The memories table has no 'content' column
    column_names = [desc[0] for desc in cursor.description]
    assert "content" not in column_names
