"""Application settings loaded from environment variables (never hard-coded)."""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration.

    Values are read from the environment or from a local ``.env`` file. Secrets are typed as
    ``SecretStr`` so they are masked in ``repr()`` and in logs.
    """

    model_config = SettingsConfigDict(env_file=".env", env_prefix="SECAUDIT_", extra="ignore")

    env: str = Field(default="dev", description="dev | test | prod")

    # Internal results store (the framework's own database, not an audit target).
    mongo_uri: SecretStr = Field(..., description="mongodb:// or mongodb+srv:// URI")
    mongo_db: str = "secaudit"
    mongo_tls: bool = True
    mongo_tls_ca_file: str | None = None
    mongo_server_selection_timeout_ms: int = 5_000

    # API auth
    jwt_public_key: SecretStr | None = None
    jwt_issuer: str = "secaudit"
    jwt_audience: str = "secaudit-api"

    # Agent safety limits
    http_timeout_s: float = 10.0
    max_requests_per_second: float = 5.0
    pan_sample_size: int = 200

    cors_origins: list[str] = ["http://localhost:5173"]


@lru_cache
def get_settings() -> Settings:
    """Return the process-wide settings singleton."""
    return Settings()  # type: ignore[call-arg]
