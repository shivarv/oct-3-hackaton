"""Normalised finding model shared by every agent."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from uuid import uuid4

from pydantic import BaseModel, Field, field_validator

from secaudit.core.redaction import redact


class Severity(StrEnum):
    """CVSS 3.1 qualitative severity bands."""

    INFO = "info"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class Finding(BaseModel):
    """A single security issue reported by an agent.

    Evidence is redacted automatically on construction, so callers cannot persist raw secrets
    by accident.
    """

    id: str = Field(default_factory=lambda: uuid4().hex)
    scan_id: str
    agent: str = Field(description="Name of the agent that produced the finding")
    title: str
    severity: Severity
    cwe: str | None = Field(default=None, pattern=r"^CWE-\d+$")
    compliance: list[str] = Field(
        default_factory=list, description="For example, ['PCI-DSS-4.0:3.5.1']"
    )
    target: str = Field(description="Scoped target identifier (repo, URL, cluster)")
    location: str | None = Field(default=None, description="file:line, endpoint or db.collection")
    evidence: str = ""
    remediation: str = ""
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @field_validator("evidence")
    @classmethod
    def _redact_evidence(cls, v: str) -> str:
        return redact(v)
