"""Entry point for running the Membrane MCP server.

Usage:
    python -m membrane

Startup flow:
    Load settings
    → Auto-generate secrets if missing
    → Initialize local metadata database
    → Initialize Walrus client
    → Initialize Sui client
    → Build managers
    → Build FastMCP server
    → Register MCP tools
    → Ready
"""

from __future__ import annotations

import asyncio
import logging
import sys

from membrane.config import load_settings
from membrane.db import init_db
from membrane.db import init_db


def main() -> None:
    """Initialize all services, build the server, and start it."""
    # Configure logging to stderr (stdout is reserved for MCP JSON-RPC over stdio)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        stream=sys.stderr,
    )
    logger = logging.getLogger("membrane")

    # 1. Load settings (auto-generates secrets if missing)
    logger.info("Loading configuration…")
    settings = load_settings()

    # 2. Initialize local metadata database
    logger.info("Initializing metadata database at: %s", settings.database_url)
    asyncio.run(init_db(settings.database_url))

    # 3. Initialize Walrus client
    from membrane.walrus_client import WalrusClient

    logger.info(
        "Initializing Walrus client (publisher=%s, aggregator=%s, epochs=%d)",
        settings.walrus_publisher_url,
        settings.walrus_aggregator_url,
        settings.walrus_storage_epochs,
    )
    walrus = WalrusClient(
        publisher_url=settings.walrus_publisher_url,
        aggregator_url=settings.walrus_aggregator_url,
        epochs=settings.walrus_storage_epochs,
    )

    # 4. Initialize Sui client
    from membrane.sui_client import SuiClient

    logger.info(
        "Initializing Sui client (rpc=%s, proofs=%s)",
        settings.sui_rpc_url,
        "enabled" if (settings.sui_wallet_address and settings.sui_private_key) else "disabled",
    )
    sui = SuiClient(
        rpc_url=settings.sui_rpc_url,
        wallet_address=settings.sui_wallet_address,
        private_key=settings.sui_private_key,
        proof_package_id=settings.sui_proof_package_id,
    )

    # 5. Build managers
    from membrane.memory_manager import MemoryManager
    from membrane.artifact_manager import ArtifactManager
    from membrane.retrieval import EmbeddingEngine, RetrievalEngine

    memory_manager = MemoryManager(walrus, sui, settings)
    artifact_manager = ArtifactManager(walrus, settings)
    embedding_engine = EmbeddingEngine(model_name=settings.embedding_model)
    retrieval_engine = RetrievalEngine(embedding_engine)

    # 6. Build Multi-Tenant ASGI App
    logger.info("Building Multi-Tenant ASGI App…")
    from membrane.app import create_app
    import uvicorn

    app = create_app(
        settings=settings,
        walrus=walrus,
        sui=sui,
        memory_manager=memory_manager,
        artifact_manager=artifact_manager,
        retrieval_engine=retrieval_engine,
    )

    # 7. Start
    # Multi-tenant routing always requires SSE transport.
    logger.info("Starting Membrane Multi-Tenant MCP server on port %s…", settings.port)
    uvicorn.run(app, host="0.0.0.0", port=settings.port)


if __name__ == "__main__":
    main()
