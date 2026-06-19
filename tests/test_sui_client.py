"""Tests for the Sui proof client."""

from __future__ import annotations

import pytest

from membrane.sui_client import SuiClient
from tests.conftest import FakeSuiClient


class TestFakeSuiClient:
    """Test the fake Sui client used in other tests."""

    @pytest.mark.asyncio
    async def test_record_and_verify(self, fake_sui):
        result = await fake_sui.record_proof(
            memory_id="mem-1",
            content_hash="abc123",
            walrus_blob_id="blob-1",
        )
        assert result is not None
        assert result.tx_hash
        assert result.proof_id

        verified = await fake_sui.verify_proof(result.tx_hash)
        assert verified is True

    @pytest.mark.asyncio
    async def test_verify_nonexistent(self, fake_sui):
        verified = await fake_sui.verify_proof("nonexistent-tx")
        assert verified is False

    @pytest.mark.asyncio
    async def test_disabled_client(self, fake_sui_disabled):
        result = await fake_sui_disabled.record_proof(
            memory_id="mem-1",
            content_hash="abc123",
            walrus_blob_id="blob-1",
        )
        assert result is None

        verified = await fake_sui_disabled.verify_proof("any-tx")
        assert verified is False


class TestSuiClientInit:
    """Test SuiClient initialisation logic."""

    def test_enabled_when_credentials_provided(self):
        client = SuiClient(
            rpc_url="http://fake",
            wallet_address="0xabc",
            private_key="base64key",
        )
        assert client.enabled is True

    def test_disabled_when_no_wallet(self):
        client = SuiClient(rpc_url="http://fake")
        assert client.enabled is False

    def test_disabled_when_partial_credentials(self):
        client = SuiClient(
            rpc_url="http://fake",
            wallet_address="0xabc",
            private_key="",
        )
        assert client.enabled is False

    @pytest.mark.asyncio
    async def test_record_proof_when_disabled(self):
        client = SuiClient(rpc_url="http://fake")
        result = await client.record_proof("mem", "hash", "blob")
        assert result is None
        await client.close()
