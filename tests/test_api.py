import pytest
from httpx import AsyncClient, ASGITransport
import asyncpg

from membrane.app import create_app
from membrane.config import MembraneSettings
from membrane.db import init_db_conn
from membrane.walrus_client import WalrusClient
from membrane.sui_client import SuiClient
from membrane.memory_manager import MemoryManager
from membrane.artifact_manager import ArtifactManager
from membrane.retrieval import RetrievalEngine, EmbeddingEngine
from tests.conftest import TEST_KEY, TEST_SECRET, FakeWalrusClient, FakeSuiClient

def stub_encode(texts):
    import numpy as np
    return np.random.rand(len(texts), 384).astype(np.float32)

@pytest.fixture
async def app_env(tmp_path):
    db_path = str(tmp_path / "test_membrane.db")
    settings = MembraneSettings(
        db_path=db_path,
        encryption_key=TEST_KEY,
        hmac_secret=TEST_SECRET,
        embedding_model="all-MiniLM-L6-v2",
        transport="sse",
    )
    
    db = await asyncpg.connect(db_path)
    db.row_factory = asyncpg.Row
    await init_db_conn(db)
    
    walrus = FakeWalrusClient()
    sui = FakeSuiClient(enabled=True)
    memory_manager = MemoryManager(walrus, sui, settings)
    artifact_manager = ArtifactManager(walrus, settings)
    embedding_engine = EmbeddingEngine(model_name=settings.embedding_model)
    retrieval_engine = RetrievalEngine(embedding_engine)
    
    app = create_app(
        settings=settings,
        walrus=walrus,
        sui=sui,
        memory_manager=memory_manager,
        artifact_manager=artifact_manager,
        retrieval_engine=retrieval_engine,
    )
    
    yield app, db, memory_manager, artifact_manager
    await db.close()

@pytest.mark.asyncio
async def test_auth_connect(app_env):
    app, db, *_ = app_env
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.post("/api/auth/connect", json={
            "wallet": "0x123",
            "signature": "sig",
            "message": "Login to Membrane"
        })
        assert res.status_code == 200
        data = res.json()
        assert data["wallet"] == "0x123"
        assert data["username"] is None
        assert data["namespace"] == "0x123"
        assert data["first_login"] is True

        # Second login
        res2 = await client.post("/api/auth/connect", json={
            "wallet": "0x123",
            "signature": "sig",
            "message": "Login to Membrane"
        })
        data2 = res2.json()
        assert data2["first_login"] is False

@pytest.mark.asyncio
async def test_claim_id(app_env):
    app, db, *_ = app_env
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Create user
        await client.post("/api/auth/connect", json={"wallet": "0x456"})
        
        res = await client.post("/api/profile/claim-id", json={
            "wallet": "0x456",
            "username": "alice"
        })
        assert res.status_code == 200
        data = res.json()
        assert data["username"] == "alice"
        assert data["namespace"] == "alice"

        # Duplicate ID should fail
        res2 = await client.post("/api/profile/claim-id", json={
            "wallet": "0x789",
            "username": "alice"
        })
        assert res2.status_code == 400

@pytest.mark.asyncio
async def test_api_keys_lifecycle(app_env):
    app, db, *_ = app_env
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Connect wallet
        await client.post("/api/auth/connect", json={"wallet": "0xabc"})
        
        # Generate key
        res = await client.post("/api/keys", json={
            "wallet": "0xabc",
            "name": "Test Key"
        })
        assert res.status_code == 200
        data = res.json()
        key = data["key"]
        assert key.startswith("mem_sk_")

        # Use key to access profile
        res_prof = await client.get("/api/profile", headers={"Authorization": f"Bearer {key}"})
        assert res_prof.status_code == 200
        assert res_prof.json()["wallet"] == "0xabc"

        # List keys
        res_list = await client.get("/api/keys", headers={"Authorization": f"Bearer {key}"})
        assert res_list.status_code == 200
        keys = res_list.json()
        assert len(keys) == 1
        key_id = keys[0]["id"]

        # Rotate key
        res_rot = await client.post("/api/keys/rotate", json={
            "wallet": "0xabc",
            "key_id": key_id
        }, headers={"Authorization": f"Bearer {key}"})
        assert res_rot.status_code == 200
        new_key = res_rot.json()["key"]
        assert new_key != key

        # Old key should be invalid
        res_prof_old = await client.get("/api/profile", headers={"Authorization": f"Bearer {key}"})
        assert res_prof_old.status_code == 401

        # New key should work
        res_prof_new = await client.get("/api/profile", headers={"Authorization": f"Bearer {new_key}"})
        assert res_prof_new.status_code == 200

@pytest.mark.asyncio
async def test_stats_and_status(app_env):
    app, db, *_ = app_env
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await client.post("/api/auth/connect", json={"wallet": "0xstat"})
        res_key = await client.post("/api/keys", json={"wallet": "0xstat", "name": "k"})
        key = res_key.json()["key"]
        
        res_stats = await client.get("/api/stats", headers={"Authorization": f"Bearer {key}"})
        assert res_stats.status_code == 200
        stats = res_stats.json()
        assert stats["memories"] == 0
        assert stats["artifacts"] == 0

        res_status = await client.get("/api/status", headers={"Authorization": f"Bearer {key}"})
        assert res_status.status_code == 200
        assert res_status.json()["online"] is True
        assert res_status.json()["walrus"] is True

@pytest.mark.asyncio
async def test_config(app_env):
    app, db, *_ = app_env
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await client.post("/api/auth/connect", json={"wallet": "0xconf"})
        res_key = await client.post("/api/keys", json={"wallet": "0xconf", "name": "k"})
        key = res_key.json()["key"]
        
        res_claude = await client.get("/api/config/claude", headers={"Authorization": f"Bearer {key}"})
        assert res_claude.status_code == 200
        assert "0xconf" in res_claude.json()["url"]

        await client.post("/api/profile/claim-id", json={"wallet": "0xconf", "username": "claimed"})
        res_claude2 = await client.get("/api/config/claude", headers={"Authorization": f"Bearer {key}"})
        assert "claimed" in res_claude2.json()["url"]
