"""Walrus decentralized storage client.

Provides an async HTTP client that wraps the Walrus publisher and aggregator
endpoints for blob upload and retrieval.  Uses ``httpx`` for non-blocking I/O.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import httpx

logger = logging.getLogger(__name__)


@dataclass
class WalrusStoreResult:
    """Result of a successful blob upload to Walrus."""

    blob_id: str
    sui_object_id: str | None = None
    end_epoch: int = 0
    already_certified: bool = False


class WalrusError(Exception):
    """Raised when a Walrus API call fails."""


class WalrusClient:
    """Async client for Walrus decentralized storage.

    Args:
        publisher_url: Base URL of the Walrus publisher service.
        aggregator_url: Base URL of the Walrus aggregator service.
        epochs: Number of storage epochs for new blobs (default 5).
        timeout: HTTP request timeout in seconds.
    """

    def __init__(
        self,
        publisher_url: str,
        aggregator_url: str,
        epochs: int = 5,
        timeout: float = 60.0,
    ) -> None:
        self._publisher_url = publisher_url.rstrip("/")
        self._aggregator_url = aggregator_url.rstrip("/")
        self._epochs = epochs
        self._client = httpx.AsyncClient(timeout=timeout)

    # ------------------------------------------------------------------
    # Store
    # ------------------------------------------------------------------

    async def store_blob(self, data: bytes) -> WalrusStoreResult:
        """Upload a blob to Walrus via the publisher.

        Sends ``PUT /v1/blobs?epochs=<N>`` and parses the JSON response
        which contains either ``newlyCreated`` or ``alreadyCertified``.

        Args:
            data: Raw bytes to store.

        Returns:
            A ``WalrusStoreResult`` with the blob ID and metadata.

        Raises:
            WalrusError: If the upload fails.
        """
        url = f"{self._publisher_url}/v1/blobs?epochs={self._epochs}"
        logger.debug("Uploading %d bytes to Walrus: %s", len(data), url)

        try:
            response = await self._client.put(
                url,
                content=data,
                headers={"Content-Type": "application/octet-stream"},
            )
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise WalrusError(
                f"Walrus upload failed (HTTP {exc.response.status_code}): "
                f"{exc.response.text}"
            ) from exc
        except httpx.RequestError as exc:
            raise WalrusError(f"Walrus upload request failed: {exc}") from exc

        body = response.json()
        return self._parse_store_response(body)

    @staticmethod
    def _parse_store_response(body: dict) -> WalrusStoreResult:
        """Extract blob ID from the publisher's JSON response."""
        if "newlyCreated" in body:
            blob_obj = body["newlyCreated"]["blobObject"]
            return WalrusStoreResult(
                blob_id=blob_obj["blobId"],
                sui_object_id=blob_obj.get("id"),
                end_epoch=blob_obj.get("storage", {}).get("endEpoch", 0),
                already_certified=False,
            )
        elif "alreadyCertified" in body:
            certified = body["alreadyCertified"]
            return WalrusStoreResult(
                blob_id=certified["blobId"],
                end_epoch=certified.get("endEpoch", 0),
                already_certified=True,
            )
        else:
            raise WalrusError(f"Unexpected Walrus response format: {body}")

    # ------------------------------------------------------------------
    # Retrieve
    # ------------------------------------------------------------------

    async def get_blob(self, blob_id: str) -> bytes:
        """Retrieve a blob from Walrus via the aggregator.

        Sends ``GET /v1/<blob_id>`` and returns the raw bytes.

        Args:
            blob_id: The Walrus blob identifier.

        Returns:
            Raw blob content as bytes.

        Raises:
            WalrusError: If retrieval fails (including 404).
        """
        url = f"{self._aggregator_url}/v1/blobs/{blob_id}"
        logger.debug("Fetching blob from Walrus: %s", url)

        try:
            response = await self._client.get(url)
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 404:
                raise WalrusError(
                    f"Blob '{blob_id}' not found on Walrus"
                ) from exc
            raise WalrusError(
                f"Walrus fetch failed (HTTP {exc.response.status_code}): "
                f"{exc.response.text}"
            ) from exc
        except httpx.RequestError as exc:
            raise WalrusError(f"Walrus fetch request failed: {exc}") from exc

        return response.content

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def close(self) -> None:
        """Close the underlying HTTP client."""
        await self._client.aclose()

    async def __aenter__(self) -> WalrusClient:
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self.close()
