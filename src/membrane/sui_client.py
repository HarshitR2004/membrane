"""Sui blockchain client for recording verification proofs.

Provides a lightweight async client that records memory content hashes
on the Sui blockchain for tamper-proof verification.  When no wallet
credentials are configured the client operates in *disabled* mode —
all proof operations return ``None`` gracefully so the rest of Membrane
continues to function without on-chain verification.
"""

from __future__ import annotations

import hashlib
import json
import logging
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone

import httpx

logger = logging.getLogger(__name__)


@dataclass
class ProofResult:
    """Result of recording a proof on Sui."""

    tx_hash: str
    proof_id: str


class SuiError(Exception):
    """Raised when a Sui RPC call fails."""


class SuiClient:
    """Lightweight async client for Sui JSON-RPC.

    When *wallet_address* or *private_key* are empty the client is
    **disabled** — :meth:`record_proof` returns ``None`` and no network
    calls are made.  This lets Membrane work out of the box without a
    funded Sui wallet.

    Args:
        rpc_url: Sui fullnode JSON-RPC URL.
        wallet_address: Sui wallet address (hex, 0x-prefixed).
        private_key: Base64-encoded Sui private key for signing.
        proof_package_id: Optional Move package ID for a deployed
            proof-store contract.
    """

    def __init__(
        self,
        rpc_url: str,
        wallet_address: str = "",
        private_key: str = "",
        proof_package_id: str = "",
    ) -> None:
        self._rpc_url = rpc_url.rstrip("/")
        self._wallet_address = wallet_address
        self._private_key = private_key
        self._proof_package_id = proof_package_id
        self._enabled = bool(wallet_address and private_key)
        self._client = httpx.AsyncClient(timeout=30.0)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def enabled(self) -> bool:
        """Return ``True`` when Sui proof recording is available."""
        return self._enabled

    async def record_proof(
        self,
        memory_id: str,
        content_hash: str,
        walrus_blob_id: str,
    ) -> ProofResult | None:
        """Record a memory integrity proof on the Sui blockchain.

        When Sui is not configured, this is a no-op and returns ``None``.

        The proof payload is a JSON-serialised object containing:
        - memory_id
        - content_hash (SHA-256 hex digest)
        - walrus_blob_id
        - timestamp (ISO-8601)

        For the hackathon demo this uses ``sui_executeTransactionBlock``
        (or a simulated transaction digest) to record the proof.  A full
        implementation would call a deployed Move contract.

        Returns:
            A :class:`ProofResult` with the Sui transaction hash and a
            locally-generated proof ID, or ``None`` if Sui is disabled.
        """
        if not self._enabled:
            logger.debug("Sui proofs disabled — skipping record_proof.")
            return None

        proof_id = str(uuid.uuid4())
        timestamp = datetime.now(timezone.utc).isoformat()

        proof_data = {
            "proof_id": proof_id,
            "memory_id": memory_id,
            "content_hash": content_hash,
            "walrus_blob_id": walrus_blob_id,
            "timestamp": timestamp,
        }

        try:
            tx_hash = await self._submit_proof(proof_data)
        except SuiError:
            logger.warning(
                "Failed to record Sui proof for memory %s — continuing without proof.",
                memory_id,
                exc_info=True,
            )
            return None

        return ProofResult(tx_hash=tx_hash, proof_id=proof_id)

    async def verify_proof(self, tx_hash: str) -> bool:
        """Verify that a proof transaction exists on Sui.

        Args:
            tx_hash: The Sui transaction digest to look up.

        Returns:
            ``True`` if the transaction exists and succeeded.
        """
        if not self._enabled:
            return False

        try:
            result = await self._rpc_call(
                "sui_getTransactionBlock",
                [tx_hash, {"showEffects": True}],
            )
            effects = result.get("effects", {})
            status = effects.get("status", {}).get("status", "")
            return status == "success"
        except SuiError:
            logger.warning(
                "Failed to verify Sui proof %s", tx_hash, exc_info=True
            )
            return False

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _submit_proof(self, proof_data: dict) -> str:
        """Submit a proof record to the Sui blockchain.

        For the hackathon this computes a deterministic "transaction
        digest" from the proof data.  When a Move package is configured
        and the full signing flow is implemented, this would construct
        a real ``MoveCall`` transaction.

        Returns:
            The transaction digest (hex string).
        """
        if self._proof_package_id:
            # Full Move-call flow (future implementation)
            return await self._move_call_proof(proof_data)

        # Hackathon mode — derive a deterministic digest for demo purposes.
        # In a production system this would be replaced by a signed
        # transaction submitted to the Sui network.
        raw = json.dumps(proof_data, sort_keys=True).encode()
        digest = hashlib.sha256(raw).hexdigest()
        logger.info(
            "Sui proof recorded (demo mode) — digest: %s", digest
        )
        return digest

    async def _move_call_proof(self, proof_data: dict) -> str:
        """Execute a Move call to a deployed proof-store contract."""
        # Build the transaction via Sui JSON-RPC
        content_hash_bytes = list(
            bytes.fromhex(proof_data["content_hash"])
        )

        result = await self._rpc_call(
            "unsafe_moveCall",
            [
                self._wallet_address,
                self._proof_package_id,
                "proof_store",
                "store_hash",
                [],                    # type arguments
                [content_hash_bytes],  # function arguments
                None,                  # gas object
                "200000000",           # gas budget
            ],
        )
        tx_digest = result.get("txDigest", result.get("digest", ""))
        if not tx_digest:
            raise SuiError(f"No transaction digest in Sui response: {result}")
        return tx_digest

    async def _rpc_call(self, method: str, params: list) -> dict:
        """Send a JSON-RPC request to the Sui fullnode."""
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": method,
            "params": params,
        }
        try:
            response = await self._client.post(
                self._rpc_url,
                json=payload,
                headers={"Content-Type": "application/json"},
            )
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise SuiError(
                f"Sui RPC failed (HTTP {exc.response.status_code}): "
                f"{exc.response.text}"
            ) from exc
        except httpx.RequestError as exc:
            raise SuiError(f"Sui RPC request failed: {exc}") from exc

        body = response.json()
        if "error" in body:
            raise SuiError(f"Sui RPC error: {body['error']}")
        return body.get("result", body)

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def close(self) -> None:
        """Close the underlying HTTP client."""
        await self._client.aclose()

    async def __aenter__(self) -> SuiClient:
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self.close()
