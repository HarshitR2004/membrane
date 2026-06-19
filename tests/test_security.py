"""Tests for the security layer — encryption, hashing, and verification."""

from __future__ import annotations

import json

import pytest
from cryptography.fernet import Fernet, InvalidToken

from membrane.db import get_db, init_db_conn
from membrane.security import (
    decrypt_content,
    delete_proof,
    encrypt_content,
    generate_content_hash,
    generate_hmac,
    get_proof,
    store_proof,
    verify_hmac,
    verify_memory_full,
)
from tests.conftest import TEST_KEY, TEST_SECRET, FakeSuiClient


# ---- Encryption tests ----

def test_encrypt_decrypt_roundtrip():
    plaintext = "sensitive memory content"
    token = encrypt_content(plaintext, TEST_KEY)
    assert token != plaintext
    result = decrypt_content(token, TEST_KEY)
    assert result == plaintext


def test_decrypt_with_wrong_key():
    token = encrypt_content("secret", TEST_KEY)
    wrong_key = Fernet.generate_key().decode()
    with pytest.raises(InvalidToken):
        decrypt_content(token, wrong_key)


def test_decrypt_tampered_token():
    token = encrypt_content("secret", TEST_KEY)
    tampered = token[:-5] + "XXXXX"
    with pytest.raises(Exception):
        decrypt_content(tampered, TEST_KEY)


# ---- Hash tests ----

def test_generate_content_hash_deterministic():
    h1 = generate_content_hash("hello")
    h2 = generate_content_hash("hello")
    assert h1 == h2


def test_generate_content_hash_different_content():
    h1 = generate_content_hash("hello")
    h2 = generate_content_hash("world")
    assert h1 != h2


def test_content_hash_is_sha256():
    import hashlib
    content = "test content"
    expected = hashlib.sha256(content.encode()).hexdigest()
    assert generate_content_hash(content) == expected


# ---- HMAC tests ----

def test_generate_hmac_deterministic():
    h1 = generate_hmac("hello", TEST_SECRET)
    h2 = generate_hmac("hello", TEST_SECRET)
    assert h1 == h2


def test_generate_hmac_different_content():
    h1 = generate_hmac("hello", TEST_SECRET)
    h2 = generate_hmac("world", TEST_SECRET)
    assert h1 != h2


def test_verify_hmac_valid():
    content = "memory content"
    digest = generate_hmac(content, TEST_SECRET)
    assert verify_hmac(content, TEST_SECRET, digest) is True


def test_verify_hmac_invalid():
    digest = generate_hmac("original", TEST_SECRET)
    assert verify_hmac("tampered", TEST_SECRET, digest) is False


# ---- Proof persistence tests ----

async def _insert_dummy_memory(db, memory_id: str) -> None:
    """Insert a minimal memory row so that FK constraints on proofs are satisfied."""
    await db.execute(
        """
        INSERT INTO memories
            (memory_id, namespace, owner, tags, timestamp,
             walrus_blob_id, content_hash)
        VALUES (?, 'default', '', '[]', '2025-01-01T00:00:00Z',
                'dummy-blob', 'dummy-hash')
        """,
        (memory_id,),
    )


@pytest.mark.asyncio
async def test_store_and_get_proof(db):
    await _insert_dummy_memory(db, "mem-123")
    proof = await store_proof(
        db,
        proof_id="proof-1",
        sui_tx_hash="0xtx1",
        memory_id="mem-123",
        content_hash="hash123",
    )
    assert proof.memory_id == "mem-123"
    assert proof.sui_tx_hash == "0xtx1"

    fetched = await get_proof(db, "mem-123")
    assert fetched is not None
    assert fetched.sui_tx_hash == "0xtx1"


@pytest.mark.asyncio
async def test_delete_proof(db):
    await _insert_dummy_memory(db, "mem-456")
    await store_proof(
        db,
        proof_id="proof-2",
        sui_tx_hash="0xtx2",
        memory_id="mem-456",
        content_hash="hash456",
    )
    await delete_proof(db, "mem-456")
    assert await get_proof(db, "mem-456") is None


# ---- Full verification tests ----

@pytest.mark.asyncio
async def test_verify_memory_full_valid(db):
    """Full verification should pass when content matches."""
    content = "my memory content"
    content_hash = generate_content_hash(content)

    # Store a proof (parent memory row needed for FK)
    await _insert_dummy_memory(db, "mem-valid")
    await store_proof(
        db,
        proof_id="proof-v1",
        sui_tx_hash="0xtx_valid",
        memory_id="mem-valid",
        content_hash=content_hash,
    )

    # Build a Walrus blob payload
    blob_payload = json.dumps({
        "memory_id": "mem-valid",
        "content": content,
        "metadata": {"extra": {}},
    }).encode()

    result = await verify_memory_full(
        db=db,
        memory_id="mem-valid",
        walrus_blob_content=blob_payload,
        stored_content_hash=content_hash,
        hmac_secret=TEST_SECRET,
        encryption_key=TEST_KEY,
        walrus_blob_id="blob-1",
    )
    assert result.verified is True
    assert result.content_hash_match is True
    assert result.walrus_blob_exists is True


@pytest.mark.asyncio
async def test_verify_memory_full_tampered(db):
    """Full verification should fail when content has been modified."""
    original = "original content"
    original_hash = generate_content_hash(original)

    await _insert_dummy_memory(db, "mem-tampered")
    await store_proof(
        db,
        proof_id="proof-v2",
        sui_tx_hash="0xtx_tampered",
        memory_id="mem-tampered",
        content_hash=original_hash,
    )

    # Blob contains tampered content
    blob_payload = json.dumps({
        "memory_id": "mem-tampered",
        "content": "modified content",
        "metadata": {"extra": {}},
    }).encode()

    result = await verify_memory_full(
        db=db,
        memory_id="mem-tampered",
        walrus_blob_content=blob_payload,
        stored_content_hash=original_hash,
        hmac_secret=TEST_SECRET,
        encryption_key=TEST_KEY,
    )
    assert result.verified is False
    assert result.content_hash_match is False


@pytest.mark.asyncio
async def test_verify_memory_walrus_unavailable(db):
    """Verification with no Walrus blob should report blob unavailable."""
    result = await verify_memory_full(
        db=db,
        memory_id="mem-no-walrus",
        walrus_blob_content=None,
        stored_content_hash="somehash",
        hmac_secret=TEST_SECRET,
        encryption_key=TEST_KEY,
    )
    assert result.verified is False
    assert result.walrus_blob_exists is False
    assert "not available" in result.message
