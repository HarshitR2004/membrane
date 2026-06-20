"""ASGI application providing multi-tenant virtual MCP endpoints.

Routes:
  /mcp/{username}/sse      -> SSE connection endpoint
  /mcp/{username}/messages -> POST endpoint for JSON-RPC messages

Each user gets a dynamically constructed FastMCP instance.
"""

from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Mount

from membrane.config import MembraneSettings
from membrane.db import get_db
from membrane.server import build_user_server
from membrane.user_context import build_user_context
from membrane.users import get_user, get_user_by_wallet, update_last_active
from membrane.api.routers import router as api_router

logger = logging.getLogger(__name__)


class MultiTenantMCPRouter:
    """Dynamically resolves and delegates to a user's FastMCP instance."""

    def __init__(
        self,
        settings: MembraneSettings,
        walrus,
        sui,
        memory_manager,
        artifact_manager,
        retrieval_engine,
    ):
        self.settings = settings
        self.walrus = walrus
        self.sui = sui
        self.memory_manager = memory_manager
        self.artifact_manager = artifact_manager
        self.retrieval_engine = retrieval_engine
        # Cache of user -> FastMCP starlette apps to avoid rebuilding on every request
        # In a very large deployment, this could use an LRU cache.
        self._app_cache = {}

    async def _get_user_app(self, username: str):
        """Get or build the Starlette app for a specific user."""
        if username in self._app_cache:
            return self._app_cache[username]

        db = await get_db(self.settings.db_path)
        try:
            user = await get_user(db, username)
            if not user:
                user = await get_user_by_wallet(db, username)
            if not user:
                return None

            # Update activity asynchronously without blocking (fire & forget could be better, but simple await here)
            await update_last_active(db, username)

            context = build_user_context(user)
            mcp = build_user_server(
                context=context,
                settings=self.settings,
                walrus=self.walrus,
                sui=self.sui,
                memory_manager=self.memory_manager,
                artifact_manager=self.artifact_manager,
                retrieval_engine=self.retrieval_engine,
            )
            # FastMCP exposes sse_app() which configures /sse and /messages
            # ASGI's Mount sets root_path automatically, so we don't pass mount_path.
            app = mcp.sse_app()
            self._app_cache[username] = app
            return app
        finally:
            await db.close()

    async def __call__(self, scope, receive, send):
        """ASGI callable."""
        assert scope["type"] == "http"
        
        # Starlette Mount strips the mount path and provides path_params if matched
        username = scope["path_params"].get("username")
        if not username:
            response = JSONResponse({"error": "Username required"}, status_code=400)
            return await response(scope, receive, send)

        app = await self._get_user_app(username)
        if not app:
            response = JSONResponse({"error": f"User '{username}' not found."}, status_code=404)
            return await response(scope, receive, send)

        # Delegate to the FastMCP Starlette app
        await app(scope, receive, send)


def create_app(
    settings: MembraneSettings,
    walrus,
    sui,
    memory_manager,
    artifact_manager,
    retrieval_engine,
) -> FastAPI:
    """Create the root FastAPI ASGI application."""
    router = MultiTenantMCPRouter(
        settings=settings,
        walrus=walrus,
        sui=sui,
        memory_manager=memory_manager,
        artifact_manager=artifact_manager,
        retrieval_engine=retrieval_engine,
    )

    app = FastAPI()
    app.state.settings = settings
    app.state.walrus = walrus
    app.state.sui = sui
    app.state.memory_manager = memory_manager
    app.state.artifact_manager = artifact_manager
    app.state.retrieval_engine = retrieval_engine

    # Add CORS middleware to allow the frontend to connect
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(api_router, prefix="/api")
    
    app.router.routes.append(
        Mount("/mcp/{username}", app=router)
    )
    return app


def create_asgi_app() -> FastAPI:
    """Zero-argument ASGI factory for Render/Gunicorn/Uvicorn.
    
    Usage: uvicorn membrane.app:create_asgi_app --factory
    """
    import asyncio
    from membrane.config import load_settings
    from membrane.db import init_db
    from membrane.walrus_client import WalrusClient
    from membrane.sui_client import SuiClient
    from membrane.memory_manager import MemoryManager
    from membrane.artifact_manager import ArtifactManager
    from membrane.retrieval import EmbeddingEngine, RetrievalEngine

    settings = load_settings()

    # Initialize DB synchronously (safe at startup before serving traffic)
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(init_db(settings.db_path))
    except RuntimeError:
        asyncio.run(init_db(settings.db_path))

    walrus = WalrusClient(
        publisher_url=settings.walrus_publisher_url,
        aggregator_url=settings.walrus_aggregator_url,
        epochs=settings.walrus_storage_epochs,
    )
    sui = SuiClient(
        rpc_url=settings.sui_rpc_url,
        wallet_address=settings.sui_wallet_address,
        private_key=settings.sui_private_key,
        proof_package_id=settings.sui_proof_package_id,
    )
    
    memory_manager = MemoryManager(walrus, sui, settings)
    artifact_manager = ArtifactManager(walrus, settings)
    embedding_engine = EmbeddingEngine(model_name=settings.embedding_model)
    retrieval_engine = RetrievalEngine(embedding_engine)

    return create_app(
        settings=settings,
        walrus=walrus,
        sui=sui,
        memory_manager=memory_manager,
        artifact_manager=artifact_manager,
        retrieval_engine=retrieval_engine,
    )
