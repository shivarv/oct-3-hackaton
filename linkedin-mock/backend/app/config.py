from __future__ import annotations

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Settings read from environment variables (MONGO_URI, MONGO_DB, SEED_DATA, ...)."""

    mongo_uri: str = "mongodb://localhost:27017"
    mongo_db: str = "linkedin_mock"
    seed_data: bool = True
    session_days: int = 7
    # Set COOKIE_SECURE=true when serving over HTTPS so the session cookie is never sent in clear.
    cookie_secure: bool = False


settings = Settings()
