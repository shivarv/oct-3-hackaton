"""Coordinates agents for a scan job and persists their findings."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Sequence
from dataclasses import dataclass

from secaudit.agents.base_agent import AgentContext, BaseAgent
from secaudit.db.MongoManager import MongoManager
from secaudit.models import Finding, OutOfScopeError

log = logging.getLogger("secaudit.orchestrator")


@dataclass(slots=True)
class AgentTask:
    """One (agent, context) pair scheduled as part of a scan."""

    agent: BaseAgent
    ctx: AgentContext


class Orchestrator:
    """Runs agent tasks concurrently with bounded parallelism and stores the results.

    A failure in one agent is isolated: it is logged and recorded on the scan document, and
    the other agents keep running. ``OutOfScopeError`` is never swallowed silently; it marks
    the scan as ``rejected``.
    """

    def __init__(self, mongo: MongoManager, max_concurrency: int = 4) -> None:
        self._mongo = mongo
        self._sem = asyncio.Semaphore(max_concurrency)

    async def run_scan(self, scan_id: str, tasks: Sequence[AgentTask]) -> list[Finding]:
        """Execute every task and persist the findings.

        Args:
            scan_id: ID of the scan document in ``scans``.
            tasks: Agents and contexts to run.

        Returns:
            All findings produced, across agents.
        """
        await self._mongo.scans.update_one({"_id": scan_id}, {"$set": {"status": "running"}})
        results = await asyncio.gather(*(self._run_one(t) for t in tasks), return_exceptions=True)

        findings: list[Finding] = []
        errors: list[dict[str, str]] = []
        status = "completed"
        for task, res in zip(tasks, results, strict=True):
            if isinstance(res, OutOfScopeError):
                status = "rejected"
                errors.append({"agent": task.agent.name, "error": str(res)})
            elif isinstance(res, BaseException):
                log.exception("agent %s failed", task.agent.name, exc_info=res)
                errors.append({"agent": task.agent.name, "error": type(res).__name__})
            else:
                findings.extend(res)

        if findings:
            await self._mongo.findings.insert_many([f.model_dump(mode="json") for f in findings])
        await self._mongo.scans.update_one(
            {"_id": scan_id},
            {"$set": {"status": status, "errors": errors, "finding_count": len(findings)}},
        )
        return findings

    async def _run_one(self, task: AgentTask) -> list[Finding]:
        async with self._sem:
            return await task.agent.run(task.ctx)
