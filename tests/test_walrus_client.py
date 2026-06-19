"""Tests for the Walrus HTTP client."""

from __future__ import annotations

import pytest

from membrane.walrus_client import WalrusClient, WalrusError, WalrusStoreResult


class TestParseStoreResponse:
    """Test response parsing without network calls."""

    def test_parse_newly_created(self):
        body = {
            "newlyCreated": {
                "blobObject": {
                    "blobId": "abc123",
                    "id": "0xobject",
                    "storage": {"endEpoch": 10},
                }
            }
        }
        result = WalrusClient._parse_store_response(body)
        assert result.blob_id == "abc123"
        assert result.sui_object_id == "0xobject"
        assert result.end_epoch == 10
        assert result.already_certified is False

    def test_parse_already_certified(self):
        body = {
            "alreadyCertified": {
                "blobId": "def456",
                "endEpoch": 20,
                "event": {"txDigest": "0xtx"},
            }
        }
        result = WalrusClient._parse_store_response(body)
        assert result.blob_id == "def456"
        assert result.end_epoch == 20
        assert result.already_certified is True

    def test_parse_unexpected_format(self):
        with pytest.raises(WalrusError, match="Unexpected"):
            WalrusClient._parse_store_response({"unknown": {}})


class TestFakeWalrusClient:
    """Test the fake client used in other tests."""

    @pytest.mark.asyncio
    async def test_store_and_get(self, fake_walrus):
        data = b"hello walrus"
        result = await fake_walrus.store_blob(data)
        assert result.blob_id

        retrieved = await fake_walrus.get_blob(result.blob_id)
        assert retrieved == data

    @pytest.mark.asyncio
    async def test_get_nonexistent(self, fake_walrus):
        with pytest.raises(WalrusError, match="not found"):
            await fake_walrus.get_blob("nonexistent")

    @pytest.mark.asyncio
    async def test_store_idempotent(self, fake_walrus):
        """Storing the same data returns the same blob_id."""
        data = b"deterministic content"
        r1 = await fake_walrus.store_blob(data)
        r2 = await fake_walrus.store_blob(data)
        assert r1.blob_id == r2.blob_id
