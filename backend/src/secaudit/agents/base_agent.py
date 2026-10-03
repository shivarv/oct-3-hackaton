"""Abstract base class shared by every audit agent."""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import ClassVar

from secaudit.models import Finding, OutOfScopeError, ScanScope, TargetKind


@dataclass(slots=True)
class AgentContext:
    """Everything an agent needs for one run. The orchestrator builds this.

    Attributes:
        scan_id: ID of the parent ``ScanJob``; it is stamped on every finding.
        scope: The authorisation boundary. Agents MUST call ``scope.require`` before any I/O.
        target: Identifier of the specific target this agent should examine.
        options: Agent-specific tuning such as rule packs, depth or sample size.
    """

    scan_id: str
    scope: ScanScope
    target: str
    options: dict[str, object] = field(default_factory=dict)


class BaseAgent(ABC):
    """Contract for an audit agent.

    Subclasses set ``name`` and ``target_kind`` and implement ``_execute``. The public ``run``
    method enforces the scope check, so a subclass cannot forget it.
    """

    name: ClassVar[str]
    target_kind: ClassVar[TargetKind]
    requires_dynamic: ClassVar[bool] = False

    def __init__(self) -> None:
        self.log = logging.getLogger(f"secaudit.agents.{self.name}")

    async def run(self, ctx: AgentContext) -> list[Finding]:
        """Validate scope, then run the agent's checks.

        Raises:
            OutOfScopeError: If ``ctx.target`` is not allowlisted, or if the agent needs dynamic
                testing that the scope does not permit.
        """
        ctx.scope.require(self.target_kind, ctx.target)
        if self.requires_dynamic and not ctx.scope.allow_dynamic:
            raise OutOfScopeError(f"{self.name} requires allow_dynamic=True in scope")
        self.log.info("starting scan_id=%s target=%s", ctx.scan_id, ctx.target)
        findings = await self._execute(ctx)
        self.log.info("finished scan_id=%s findings=%d", ctx.scan_id, len(findings))
        return findings

    @abstractmethod
    async def _execute(self, ctx: AgentContext) -> list[Finding]:
        """Run the agent's checks. Implementations must be read-only against the target."""

    def finding(self, ctx: AgentContext, **kwargs: object) -> Finding:
        """Build a ``Finding`` with the scan ID, agent name and target already filled in."""
        return Finding(scan_id=ctx.scan_id, agent=self.name, target=ctx.target, **kwargs)  # type: ignore[arg-type]
