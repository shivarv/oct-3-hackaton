"""Secure MongoDB connection management. This is the ONLY module allowed to import ``pymongo``.

Two kinds of connection are handled:

* **Results store**: the framework's own database, used for scans and findings. It uses the
  app-wide URI from ``Settings``.
* **Audit targets**: third-party clusters under test. They use a per-scope, read-only
  credential and are opened only after a scope check.
"""

from __future__ import annotations

import re
from collections.abc import AsyncIterator, Mapping
from contextlib import asynccontextmanager
from typing import Any, Final

from pymongo import AsyncMongoClient
from pymongo.asynchronous.collection import AsyncCollection
from pymongo.asynchronous.database import AsyncDatabase

from secaudit.core.config import Settings, get_settings
from secaudit.core.redaction import redact
from secaudit.models import ScanScope, TargetKind

Document = dict[str, Any]
TargetClient = AsyncMongoClient[Document]
"""Type alias re-exported so agents can annotate clients without importing pymongo."""

FORBIDDEN_OPERATORS: Final[frozenset[str]] = frozenset({"$where", "$function", "$accumulator"})
_SAFE_NAME = re.compile(r"^[A-Za-z0-9_-]{1,64}$")


class UnsafeQueryError(ValueError):
    """Raised when a filter contains server-side JS operators or other disallowed constructs."""


def assert_safe_filter(filter_: Mapping[str, Any]) -> None:
    """Recursively reject server-side JavaScript operators in a query filter.

    Args:
        filter_: A MongoDB filter document.

    Raises:
        UnsafeQueryError: If a forbidden operator appears at any depth.
    """
    stack: list[Any] = [filter_]
    while stack:
        node = stack.pop()
        if isinstance(node, Mapping):
            for k, v in node.items():
                if k in FORBIDDEN_OPERATORS:
                    raise UnsafeQueryError(f"operator {k} is not allowed")
                stack.append(v)
        elif isinstance(node, list | tuple):
            stack.extend(node)


class MongoManager:
    """Owns the MongoDB clients and enforces secure connection defaults.

    Security defaults:
        * TLS is required outside ``env=dev``. Invalid certificates are never allowed.
        * ``retryWrites`` is on, and server selection and socket timeouts are bounded.
        * Connection strings are redacted in every log line and exception message.
        * Target connections use ``readPreference=secondaryPreferred`` and are read-only by contract.

    Usage:
        >>> mm = MongoManager()
        >>> await mm.connect()
        >>> await mm.findings.insert_one(finding.model_dump())
        >>> await mm.close()
    """

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()
        self._client: AsyncMongoClient[Document] | None = None

    # ------------------------------------------------------------------ results store
    async def connect(self) -> None:
        """Open the results-store client and verify connectivity with ``ping``.

        Raises:
            RuntimeError: With a redacted message if the server cannot be reached.
        """
        s = self._settings
        if s.env != "dev" and not s.mongo_tls:
            raise RuntimeError("TLS must be enabled for MongoDB outside dev")
        self._client = AsyncMongoClient(
            s.mongo_uri.get_secret_value(),
            tls=s.mongo_tls,
            tlsCAFile=s.mongo_tls_ca_file,
            tlsAllowInvalidCertificates=False,
            serverSelectionTimeoutMS=s.mongo_server_selection_timeout_ms,
            socketTimeoutMS=30_000,
            retryWrites=True,
            appname="secaudit",
        )
        try:
            await self._client.admin.command("ping")
        except Exception as exc:
            raise RuntimeError(f"MongoDB connection failed: {redact(str(exc))}") from None

    async def close(self) -> None:
        if self._client is not None:
            await self._client.close()
            self._client = None

    @property
    def db(self) -> AsyncDatabase[Document]:
        if self._client is None:
            raise RuntimeError("MongoManager.connect() has not been called")
        return self._client[self._settings.mongo_db]

    @property
    def findings(self) -> AsyncCollection[Document]:
        return self.db["findings"]

    @property
    def scans(self) -> AsyncCollection[Document]:
        return self.db["scans"]

    async def ensure_indexes(self) -> None:
        """Create the indexes the API relies on. Safe to run more than once."""
        await self.findings.create_index([("scan_id", 1), ("severity", 1)])
        await self.findings.create_index("created_at")
        await self.scans.create_index("status")

    async def find_safe(
        self, collection: str, filter_: Mapping[str, Any], *, limit: int = 100
    ) -> list[Document]:
        """Run a validated, bounded ``find`` on the results store.

        Args:
            collection: Collection name (alphanumeric, underscore or hyphen).
            filter_: Filter built from *validated* values, never raw request JSON.
            limit: Maximum number of documents to return (capped at 1000).
        """
        if not _SAFE_NAME.match(collection):
            raise UnsafeQueryError("invalid collection name")
        assert_safe_filter(filter_)
        cursor = self.db[collection].find(dict(filter_), limit=min(limit, 1000))
        return await cursor.to_list()

    # ------------------------------------------------------------------ audit targets
    @asynccontextmanager
    async def target_client(
        self, scope: ScanScope, target: str, uri: str
    ) -> AsyncIterator[AsyncMongoClient[Document]]:
        """Open a short-lived client to an in-scope audit target.

        Args:
            scope: Active scan scope. ``target`` must be allowlisted as ``TargetKind.MONGO``.
            target: Scoped identifier, for example ``"db.prod.internal:27017/payments"``.
            uri: Connection URI resolved from ``ScopedTarget.credential_ref`` by the caller's
                secret provider. It is never logged.

        Yields:
            A client configured for read-only auditing.
        """
        scope.require(TargetKind.MONGO, target)
        client: AsyncMongoClient[Document] = AsyncMongoClient(
            uri,
            tls=True,
            tlsAllowInvalidCertificates=False,
            readPreference="secondaryPreferred",
            serverSelectionTimeoutMS=self._settings.mongo_server_selection_timeout_ms,
            appname="secaudit-auditor",
        )
        try:
            yield client
        finally:
            await client.close()
