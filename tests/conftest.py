"""Shared test fixtures for Membrane tests.

Provides mock implementations of WalrusClient and SuiClient that store
data in-memory, along with common settings and database fixtures.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from typing import Any
from unittest.mock import patch

import numpy as np
import pytest
from cryptography.fernet import Fernet

from membrane.config import MembraneSettings
from membrane.db import get_db, init_db_conn
from membrane.walrus_client import WalrusClient, WalrusStoreResult, WalrusError
from membrane.sui_client import SuiClient, ProofResult


# ---------------------------------------------------------------------------
# Test keys
# ---------------------------------------------------------------------------

TEST_KEY = Fernet.generate_key().decode()
TEST_SECRET = "test-hmac-secret-key-for-membrane"


# ---------------------------------------------------------------------------
# Fake Walrus client
# ---------------------------------------------------------------------------

class FakeWalrusClient:
    """In-memory Walrus client for testing — no network calls."""

    def __init__(self) -> None:
        self._blobs: dict[str, bytes] = {}

    async def store_blob(self, data: bytes) -> WalrusStoreResult:
        blob_id = hashlib.sha256(data).hexdigest()[:32]
        self._blobs[blob_id] = data
        return WalrusStoreResult(
            blob_id=blob_id,
            sui_object_id=f"0x{blob_id[:16]}",
            end_epoch=5,
            already_certified=False,
        )

    async def get_blob(self, blob_id: str) -> bytes:
        if blob_id not in self._blobs:
            raise WalrusError(f"Blob '{blob_id}' not found")
        return self._blobs[blob_id]

    async def close(self) -> None:
        pass


# ---------------------------------------------------------------------------
# Fake Sui client
# ---------------------------------------------------------------------------

class FakeSuiClient:
    """In-memory Sui client for testing — no network calls."""

    def __init__(self, enabled: bool = True) -> None:
        self._enabled = enabled
        self._proofs: dict[str, dict] = {}

    @property
    def enabled(self) -> bool:
        return self._enabled

    async def record_proof(
        self,
        memory_id: str,
        content_hash: str,
        walrus_blob_id: str,
    ) -> ProofResult | None:
        if not self._enabled:
            return None
        proof_id = str(uuid.uuid4())
        tx_hash = hashlib.sha256(
            f"{memory_id}{content_hash}".encode()
        ).hexdigest()
        self._proofs[proof_id] = {
            "tx_hash": tx_hash,
            "memory_id": memory_id,
            "content_hash": content_hash,
            "walrus_blob_id": walrus_blob_id,
        }
        return ProofResult(tx_hash=tx_hash, proof_id=proof_id)

    async def verify_proof(self, tx_hash: str) -> bool:
        return any(
            p["tx_hash"] == tx_hash for p in self._proofs.values()
        )

    async def close(self) -> None:
        pass


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def fake_walrus():
    """Provide a fresh in-memory Walrus client."""
    return FakeWalrusClient()


@pytest.fixture()
def fake_sui():
    """Provide a fresh in-memory Sui client (enabled)."""
    return FakeSuiClient(enabled=True)


@pytest.fixture()
def fake_sui_disabled():
    """Provide a Sui client with proofs disabled."""
    return FakeSuiClient(enabled=False)


@pytest.fixture()
def settings(tmp_path):
    """Provide test settings with a temporary file-based DB."""
    db_path = str(tmp_path / "test_membrane.db")
    return MembraneSettings(
        db_path=db_path,
        encryption_key=TEST_KEY,
        hmac_secret=TEST_SECRET,
        embedding_model="all-MiniLM-L6-v2",
        default_retrieval_limit=10,
        transport="stdio",
        walrus_publisher_url="http://fake-publisher",
        walrus_aggregator_url="http://fake-aggregator",
        walrus_storage_epochs=5,
        sui_rpc_url="http://fake-sui-rpc",
        sui_wallet_address="",
        sui_private_key="",
        default_owner="test-owner",
        default_namespace="test-ns",
    )


@pytest.fixture()
async def db():
    """Provide a fresh in-memory database for each test."""
    conn = await get_db(":memory:")
    await init_db_conn(conn)
    yield conn
    await conn.close()


@pytest.fixture()
async def file_db(settings):
    """Provide a file-based database (needed for some server tests)."""
    from membrane.db import init_db
    await init_db(settings.db_path)
    conn = await get_db(settings.db_path)
    yield conn
    await conn.close()


def stub_encode(self, text: str) -> np.ndarray:
    """Deterministic fake embedding to avoid loading the real model in CI."""
    h = hashlib.sha256(text.encode()).digest()
    rng = np.random.default_rng(int.from_bytes(h[:4], "big"))
    return rng.random(384).astype(np.float32)
