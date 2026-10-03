"""Scan scope: the authorisation boundary that every agent must respect."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from urllib.parse import urlparse

from pydantic import BaseModel, Field


class OutOfScopeError(PermissionError):
    """Raised when an agent is asked to touch a target outside the approved scope."""


class TargetKind(StrEnum):
    REPO = "repo"
    URL = "url"
    MONGO = "mongo"


class ScopedTarget(BaseModel):
    kind: TargetKind
    identifier: str = Field(description="Repo path or URL, URL origin, or Mongo host[:port]/db")
    credential_ref: str | None = Field(
        default=None, description="Name of a secret in the vault, never the secret itself"
    )


class ScanScope(BaseModel):
    """An approved, time-boxed list of targets plus the person who authorised it.

    Attributes:
        owner: Accountable person or team for the systems under test.
        authorization_ref: Ticket or engagement ID proving written permission.
        targets: Explicit allowlist. Anything not listed is out of scope.
        expires_at: The scope is invalid after this moment.
        allow_dynamic: If False, agents may run only static analysis.
    """

    owner: str
    authorization_ref: str
    targets: list[ScopedTarget]
    expires_at: datetime
    allow_dynamic: bool = False

    def is_in_scope(self, kind: TargetKind, identifier: str) -> bool:
        """Return True if ``identifier`` matches an allowlisted target of the same kind and the scope is still valid."""
        return self._match(kind, identifier) is not None

    def require(self, kind: TargetKind, identifier: str) -> ScopedTarget:
        """Return the matching scoped target, or raise ``OutOfScopeError``."""
        target = self._match(kind, identifier)
        if target is None:
            raise OutOfScopeError(f"{kind}:{identifier} is not in scope {self.authorization_ref}")
        return target

    def _match(self, kind: TargetKind, identifier: str) -> ScopedTarget | None:
        if datetime.now(UTC) >= self.expires_at:
            return None
        norm = self._normalise(kind, identifier)
        for t in self.targets:
            allowed = self._normalise(kind, t.identifier)
            # Match on a path boundary only, so "db" does not also allow "db2".
            if t.kind == kind and (norm == allowed or norm.startswith(allowed.rstrip("/") + "/")):
                return t
        return None

    @staticmethod
    def _normalise(kind: TargetKind, identifier: str) -> str:
        if kind is TargetKind.URL:
            p = urlparse(identifier)
            return (
                f"{p.scheme.lower()}://{(p.hostname or '').lower()}:{p.port or ''}{p.path or '/'}"
            )
        return identifier.strip().lower().rstrip("/")
