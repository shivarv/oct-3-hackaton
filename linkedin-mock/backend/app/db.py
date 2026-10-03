from __future__ import annotations

import asyncio
import logging
from typing import Any

from pymongo import AsyncMongoClient
from pymongo.asynchronous.database import AsyncDatabase
from pymongo.errors import PyMongoError

from .config import settings

log = logging.getLogger(__name__)


class Mongo:
    """Holds the single MongoDB client for the app."""

    def __init__(self) -> None:
        self._client: AsyncMongoClient[dict[str, Any]] | None = None

    async def connect(self, attempts: int = 10) -> None:
        for attempt in range(1, attempts + 1):
            client: AsyncMongoClient[dict[str, Any]] = AsyncMongoClient(
                settings.mongo_uri, serverSelectionTimeoutMS=3000, tz_aware=True
            )
            try:
                await client[settings.mongo_db].command("ping")
            except PyMongoError as exc:
                await client.close()
                log.warning("MongoDB not ready (attempt %d/%d): %s", attempt, attempts, exc)
                await asyncio.sleep(2)
                continue
            self._client = client
            return
        raise RuntimeError("Could not connect to MongoDB")

    @property
    def db(self) -> AsyncDatabase[dict[str, Any]]:
        if self._client is None:
            raise RuntimeError("MongoDB client is not connected")
        return self._client[settings.mongo_db]

    async def ensure_indexes(self) -> None:
        # Usernames are optional, so uniqueness only applies to documents that have one.
        await self.db.users.create_index(
            "username", unique=True, partialFilterExpression={"username": {"$type": "string"}}
        )
        # MongoDB's TTL monitor deletes sessions once expires_at has passed.
        await self.db.sessions.create_index("expires_at", expireAfterSeconds=0)
        await self.db.posts.create_index([("created_at", -1)])
        await self.db.posts.create_index([("author_id", 1), ("created_at", -1)])

    async def close(self) -> None:
        if self._client is not None:
            await self._client.close()
            self._client = None


mongo = Mongo()
