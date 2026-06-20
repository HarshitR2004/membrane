"""Configuration management for Membrane.

Loads settings from environment variables and .env file using pydantic-settings.
Auto-generates cryptographic keys on first run if not provided.
"""

from __future__ import annotations

import base64
import os
import secrets
from pathlib import Path

from cryptography.fernet import Fernet
from pydantic_settings import BaseSettings, SettingsConfigDict

# Project root is two levels up from src/membrane/config.py
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


class MembraneSettings(BaseSettings):
    """Application settings loaded from environment / .env file."""

    model_config = SettingsConfigDict(
        env_prefix="MEMBRANE_",
        env_file=str(_PROJECT_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Database (metadata only)
    database_url: str = ""

    # Security — auto-generated if left empty
    encryption_key: str = ""
    hmac_secret: str = ""

    # Embeddings
    embedding_model: str = "all-MiniLM-L6-v2"

    # Retrieval
    default_retrieval_limit: int = 10

    # MCP transport
    transport: str = "sse"
    port: int = 8000

    # ── Walrus (canonical storage) ──────────────────────────────────────
    walrus_publisher_url: str = "https://publisher.walrus-testnet.walrus.space"
    walrus_aggregator_url: str = "https://aggregator.walrus-testnet.walrus.space"
    walrus_storage_epochs: int = 5

    # ── Sui (verification) ─────────────────────────────────────────────
    sui_rpc_url: str = "https://fullnode.testnet.sui.io:443"
    sui_wallet_address: str = ""
    sui_private_key: str = ""
    sui_proof_package_id: str = ""

    # ── Identity defaults ──────────────────────────────────────────────
    default_owner: str = "membrane-local"
    default_namespace: str = "default"

    def ensure_secrets(self) -> None:
        """Generate and persist cryptographic secrets if they are missing.

        Writes generated values back to the .env file so they survive restarts.
        """
        changed = False

        if not self.encryption_key:
            self.encryption_key = Fernet.generate_key().decode()
            changed = True

        if not self.hmac_secret:
            self.hmac_secret = base64.urlsafe_b64encode(
                secrets.token_bytes(32)
            ).decode()
            changed = True

        if changed:
            self._persist_secrets()

    def _persist_secrets(self) -> None:
        """Append generated secrets to the .env file."""
        env_path = _PROJECT_ROOT / ".env"
        lines: list[str] = []

        if env_path.exists():
            lines = env_path.read_text(encoding="utf-8").splitlines()

        key_map = {
            "MEMBRANE_ENCRYPTION_KEY": self.encryption_key,
            "MEMBRANE_HMAC_SECRET": self.hmac_secret,
        }

        for key, value in key_map.items():
            # Replace existing line or append
            found = False
            for i, line in enumerate(lines):
                if line.startswith(f"{key}="):
                    lines[i] = f"{key}={value}"
                    found = True
                    break
            if not found:
                lines.append(f"{key}={value}")

        env_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def load_settings() -> MembraneSettings:
    """Load settings and ensure cryptographic secrets exist."""
    settings = MembraneSettings()

    # Resolve relative db_path against the project root so it works
    # regardless of the working directory the process is started from
    # (e.g. when spawned by an MCP client like the Inspector, Claude
    # Desktop, or Cursor).
    # (e.g. when spawned by an MCP client like the Inspector, Claude
    # Desktop, or Cursor).

    settings.ensure_secrets()
    return settings
