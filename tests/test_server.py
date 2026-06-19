"""End-to-end tests for the MCP server tools.

These tests create a real FastMCP server instance backed by fake Walrus
and Sui clients, and invoke all 9 tools via ``server.call_tool()``.
"""

from __future__ import annotations

import json
from unittest.mock import patch

import numpy as np
import pytest

from membrane.artifact_manager import ArtifactManager
from membrane.config import MembraneSettings
from membrane.db import init_db
from membrane.memory_manager import MemoryManager
from membrane.retrieval import EmbeddingEngine, RetrievalEngine
from membrane.server import build_user_server
from membrane.users import create_user
from membrane.user_context import build_user_context
from membrane.db import get_db
from tests.conftest import (
    TEST_KEY,
    TEST_SECRET,
    FakeSuiClient,
    FakeWalrusClient,
    stub_encode,
)


@pytest.fixture()
async def server_env(tmp_path):
    """Set up a full server environment with fake backends."""
    db_path = str(tmp_path / "test_membrane.db")
    settings = MembraneSettings(
        db_path=db_path,
        encryption_key=TEST_KEY,
        hmac_secret=TEST_SECRET,
        embedding_model="all-MiniLM-L6-v2",
        default_retrieval_limit=10,
        transport="stdio",
        walrus_publisher_url="http://fake-publisher",
        walrus_aggregator_url="http://fake-aggregator",
        walrus_storage_epochs=5,
        default_owner="test-owner",
        default_namespace="test-ns",
    )
    await init_db(settings.db_path)
    db = await get_db(settings.db_path)
    user = await create_user(db, wallet_address="0xowner", username="test-owner", namespace="test-ns")
    
    # We also need a second user for tests testing list_agents
    await create_user(db, wallet_address="0xagenty", username="agent_y", namespace="test-ns")
    
    await db.close()

    context = build_user_context(user)

    walrus = FakeWalrusClient()
    sui = FakeSuiClient(enabled=True)
    memory_mgr = MemoryManager(walrus, sui, settings)
    artifact_mgr = ArtifactManager(walrus, settings)
    embedding_engine = EmbeddingEngine(model_name=settings.embedding_model)
    retrieval = RetrievalEngine(embedding_engine)

    server = build_user_server(
        context=context,
        settings=settings,
        walrus=walrus,
        sui=sui,
        memory_manager=memory_mgr,
        artifact_manager=artifact_mgr,
        retrieval_engine=retrieval,
    )

    return server, settings, walrus, sui


def _parse_result(result) -> dict:
    """Extract the dict payload from a call_tool result."""
    if isinstance(result, dict):
        return result
    if isinstance(result, tuple):
        if len(result) > 1 and isinstance(result[1], dict):
            return result[1]
        result = result[0]

    for block in result:
        if hasattr(block, "text"):
            return json.loads(block.text)
    raise ValueError(f"Unexpected call_tool result type: {type(result)}")


# ------------------------------------------------------------------
# store_memory + get via search
# ------------------------------------------------------------------


@pytest.mark.asyncio
@patch("membrane.retrieval.EmbeddingEngine.encode", stub_encode)
async def test_store_memory(server_env):
    server, *_ = server_env

    result = _parse_result(await server.call_tool(
        "store_memory",
        {
            "content": "The capital of France is Paris.",
            "tags": ["geography"],
            "metadata": {"category": "geography"},
        },
    ))
    assert result["status"] == "stored"
    assert result["memory_id"]
    assert result["walrus_blob_id"]
    assert result["namespace"] == "test-ns"


# ------------------------------------------------------------------
# store + search_memory
# ------------------------------------------------------------------


@pytest.mark.asyncio
@patch("membrane.retrieval.EmbeddingEngine.encode", stub_encode)
async def test_search_memory(server_env):
    server, *_ = server_env

    await server.call_tool(
        "store_memory", {"content": "Python is a programming language"}
    )
    await server.call_tool(
        "store_memory", {"content": "The Eiffel Tower is in Paris"}
    )

    result = _parse_result(await server.call_tool(
        "search_memory", {"query": "programming", "limit": 2},
    ))
    assert "memories" in result
    assert len(result["memories"]) <= 2


# ------------------------------------------------------------------
# store + update
# ------------------------------------------------------------------


@pytest.mark.asyncio
@patch("membrane.retrieval.EmbeddingEngine.encode", stub_encode)
async def test_update_memory(server_env):
    server, *_ = server_env

    store_result = _parse_result(await server.call_tool(
        "store_memory", {"content": "v1"},
    ))
    memory_id = store_result["memory_id"]

    update_result = _parse_result(await server.call_tool(
        "update_memory",
        {"memory_id": memory_id, "content": "v2", "tags": ["updated"]},
    ))
    assert update_result["status"] == "updated"


# ------------------------------------------------------------------
# delete
# ------------------------------------------------------------------


@pytest.mark.asyncio
@patch("membrane.retrieval.EmbeddingEngine.encode", stub_encode)
async def test_delete_memory(server_env):
    server, *_ = server_env

    store_result = _parse_result(await server.call_tool(
        "store_memory", {"content": "to delete"},
    ))
    memory_id = store_result["memory_id"]

    del_result = _parse_result(await server.call_tool(
        "delete_memory", {"memory_id": memory_id},
    ))
    assert del_result["status"] == "deleted"


# ------------------------------------------------------------------
# verify_memory
# ------------------------------------------------------------------


@pytest.mark.asyncio
@patch("membrane.retrieval.EmbeddingEngine.encode", stub_encode)
async def test_verify_memory(server_env):
    server, *_ = server_env

    store_result = _parse_result(await server.call_tool(
        "store_memory", {"content": "verify me"},
    ))
    memory_id = store_result["memory_id"]

    verify_result = _parse_result(await server.call_tool(
        "verify_memory", {"memory_id": memory_id},
    ))
    assert verify_result["verified"] is True
    assert verify_result["content_hash_match"] is True
    assert verify_result["walrus_blob_exists"] is True


# ------------------------------------------------------------------
# store_artifact + get_artifact
# ------------------------------------------------------------------


@pytest.mark.asyncio
@patch("membrane.retrieval.EmbeddingEngine.encode", stub_encode)
async def test_store_and_get_artifact(server_env):
    server, *_ = server_env

    store_result = _parse_result(await server.call_tool(
        "store_artifact",
        {
            "content": "A very large document " * 500,
            "filename": "report.pdf",
            "metadata": {"format": "text"},
        },
    ))
    assert store_result["status"] == "stored"
    artifact_id = store_result["artifact_id"]

    got = _parse_result(await server.call_tool(
        "get_artifact", {"artifact_id": artifact_id},
    ))
    assert got["artifact_id"] == artifact_id
    assert got["metadata"]["format"] == "text"
    assert got["filename"] == "report.pdf"


# ------------------------------------------------------------------
# list_memories
# ------------------------------------------------------------------


@pytest.mark.asyncio
@patch("membrane.retrieval.EmbeddingEngine.encode", stub_encode)
async def test_list_memories(server_env):
    server, *_ = server_env

    await server.call_tool(
        "store_memory", {"content": "mem1"}
    )
    await server.call_tool(
        "store_memory", {"content": "mem2"}
    )

    result = _parse_result(await server.call_tool(
        "list_memories", {}
    ))
    assert result["total"] == 2




# ------------------------------------------------------------------
# list_artifacts
# ------------------------------------------------------------------


@pytest.mark.asyncio
@patch("membrane.retrieval.EmbeddingEngine.encode", stub_encode)
async def test_list_artifacts(server_env):
    server, *_ = server_env

    await server.call_tool(
        "store_artifact", {"content": "art1"}
    )
    await server.call_tool(
        "store_artifact", {"content": "art2"}
    )

    result = _parse_result(await server.call_tool(
        "list_artifacts", {}
    ))
    assert result["total"] == 2


# ------------------------------------------------------------------
# Error cases
# ------------------------------------------------------------------


@pytest.mark.asyncio
@patch("membrane.retrieval.EmbeddingEngine.encode", stub_encode)
async def test_delete_nonexistent_memory(server_env):
    server, *_ = server_env
    result = _parse_result(await server.call_tool(
        "delete_memory", {"memory_id": "does-not-exist"},
    ))
    assert "error" in result


@pytest.mark.asyncio
@patch("membrane.retrieval.EmbeddingEngine.encode", stub_encode)
async def test_get_nonexistent_artifact(server_env):
    server, *_ = server_env
    result = _parse_result(await server.call_tool(
        "get_artifact", {"artifact_id": "does-not-exist"},
    ))
    assert "error" in result


@pytest.mark.asyncio
@patch("membrane.retrieval.EmbeddingEngine.encode", stub_encode)
async def test_verify_nonexistent_memory(server_env):
    server, *_ = server_env
    result = _parse_result(await server.call_tool(
        "verify_memory", {"memory_id": "does-not-exist"},
    ))
    assert "error" in result


# ------------------------------------------------------------------
# Encrypted memory
# ------------------------------------------------------------------


@pytest.mark.asyncio
@patch("membrane.retrieval.EmbeddingEngine.encode", stub_encode)
async def test_store_encrypted_memory(server_env):
    server, *_ = server_env

    result = _parse_result(await server.call_tool(
        "store_memory",
        {"content": "Secret: the answer is 42", "encrypt": True},
    ))
    assert result["status"] == "stored"
    memory_id = result["memory_id"]

    # Search should decrypt for display
    search = _parse_result(await server.call_tool(
        "search_memory", {"query": "answer"},
    ))
    assert "memories" in search
    # At least one memory should have the decrypted content
    contents = [m["content"] for m in search["memories"]]
    assert "Secret: the answer is 42" in contents


# ------------------------------------------------------------------
# Graph and Observability Tools
# ------------------------------------------------------------------

@pytest.mark.asyncio
@patch("membrane.retrieval.EmbeddingEngine.encode", stub_encode)
async def test_observability_tools(server_env):
    server, *_ = server_env

    # 1. Store a memory
    store_result_1 = _parse_result(await server.call_tool(
        "store_memory", {"content": "Node A"}
    ))
    mem_1 = store_result_1["memory_id"]

    # 2. Store another memory with a relation to the first
    store_result_2 = _parse_result(await server.call_tool(
        "store_memory", {"content": "Node B", "relations": [{"target_id": mem_1, "type": "references"}]}
    ))
    mem_2 = store_result_2["memory_id"]

    # 3. Store an artifact (workflow)
    await server.call_tool(
        "store_artifact", {"content": "state", "type": "workflow"}
    )

    # test inspect_memory
    inspect = _parse_result(await server.call_tool("inspect_memory", {"memory_id": mem_2}))
    assert inspect["memory_id"] == mem_2
    assert len(inspect["relations"]) == 1
    assert inspect["relations"][0]["target_id"] == mem_1

    # test show_graph
    graph = _parse_result(await server.call_tool("show_graph", {"memory_id": mem_2, "depth": 1}))
    assert len(graph["nodes"]) == 2
    assert len(graph["edges"]) == 1

    # test list_agents
    agents = _parse_result(await server.call_tool("list_agents", {}))
    assert "0xowner" in agents["agents"]

    # test list_workflows
    workflows = _parse_result(await server.call_tool("list_workflows", {}))
    assert workflows["total"] == 1
    assert workflows["workflows"][0]["type"] == "workflow"

