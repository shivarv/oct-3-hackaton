"""Static analysis agent for React / JavaScript client-side code.

Playbook: ``.claude/skills/react-frontend-audit/SKILL.md``.
"""

from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass
from pathlib import Path
from typing import ClassVar

from secaudit.agents.base_agent import AgentContext, BaseAgent
from secaudit.models import Finding, Severity, TargetKind


@dataclass(frozen=True, slots=True)
class SinkRule:
    """A regex-based rule for a dangerous client-side sink or pattern.

    Attributes:
        rule_id: Stable identifier, for example ``"react.dangerously-set-inner-html"``.
        pattern: Compiled regex applied line by line.
        title: Human-readable finding title.
        cwe: CWE identifier.
        severity: Default severity before contextual adjustment.
        remediation: Fix guidance shown in the report.
    """

    rule_id: str
    pattern: re.Pattern[str]
    title: str
    cwe: str
    severity: Severity
    remediation: str


DEFAULT_RULES: tuple[SinkRule, ...] = (
    SinkRule(
        "react.dangerously-set-inner-html",
        re.compile(r"dangerouslySetInnerHTML"),
        "Raw HTML injected via dangerouslySetInnerHTML",
        "CWE-79",
        Severity.HIGH,
        "Render as text, or sanitise with DOMPurify immediately before the sink.",
    ),
    SinkRule(
        "js.eval",
        re.compile(r"\beval\s*\(|new\s+Function\s*\("),
        "Dynamic code evaluation",
        "CWE-95",
        Severity.HIGH,
        "Remove eval/new Function; parse data with JSON.parse instead.",
    ),
    SinkRule(
        "dom.inner-html",
        re.compile(r"\.(innerHTML|outerHTML)\s*=|insertAdjacentHTML\s*\("),
        "Direct DOM HTML assignment",
        "CWE-79",
        Severity.MEDIUM,
        "Use textContent or React rendering instead of HTML string assignment.",
    ),
    SinkRule(
        "storage.token",
        re.compile(r"(local|session)Storage\.setItem\(\s*['\"][^'\"]*(token|jwt|auth)", re.I),
        "Auth token stored in Web Storage",
        "CWE-922",
        Severity.MEDIUM,
        "Store session tokens in HttpOnly, Secure, SameSite cookies.",
    ),
    SinkRule(
        "postmessage.wildcard",
        re.compile(r"postMessage\([^)]*,\s*['\"]\*['\"]"),
        "postMessage with wildcard target origin",
        "CWE-346",
        Severity.MEDIUM,
        "Pass the exact expected origin as targetOrigin.",
    ),
    SinkRule(
        "env.public-secret",
        re.compile(r"(VITE_|REACT_APP_|NEXT_PUBLIC_)\w*(SECRET|PRIVATE|PASSWORD|TOKEN)\w*", re.I),
        "Secret exposed through a public build-time env variable",
        "CWE-200",
        Severity.HIGH,
        "Move the secret server-side; public env vars are bundled into client JS.",
    ),
)


class FrontendScannerAgent(BaseAgent):
    """Analyses React frontend source and build artefacts for client-side vulnerabilities.

    Scope kind: ``TargetKind.REPO`` (a local checkout path). The agent never executes
    project code or installs packages from the target. All analysis is read-only.

    Checks (planned):
        1. Dangerous sinks: ``dangerouslySetInnerHTML``, ``eval``, ``innerHTML`` (``DEFAULT_RULES``).
        2. Secrets in source, ``.env*`` files and built bundles.
        3. Production source maps in ``dist/``/``build/``.
        4. Vulnerable dependencies via ``npm audit`` / OSV lockfile scan.
        5. Insecure token storage and ``postMessage`` handling.
        6. Missing or weak CSP (needs a URL target and ``allow_dynamic``; delegated).

    Options (``ctx.options``):
        include_globs (list[str]): Files to scan. Default ``["src/**/*.{js,jsx,ts,tsx}"]``.
        scan_build (bool): Also scan ``dist/``/``build/`` output. Default ``True``.
        max_file_bytes (int): Skip files larger than this. Default 2 MiB.
    """

    name: ClassVar[str] = "frontend_scanner"
    target_kind: ClassVar[TargetKind] = TargetKind.REPO

    SOURCE_SUFFIXES: ClassVar[frozenset[str]] = frozenset({".js", ".jsx", ".ts", ".tsx", ".mjs"})

    def __init__(self, rules: tuple[SinkRule, ...] = DEFAULT_RULES) -> None:
        super().__init__()
        self.rules = rules

    async def _execute(self, ctx: AgentContext) -> list[Finding]:
        root = await asyncio.to_thread(Path(ctx.target).resolve)
        # Filesystem walking is blocking, so run it off the event loop.
        findings = await asyncio.to_thread(self._scan_tree, ctx, root)
        findings.extend(await self.audit_dependencies(ctx, root))
        findings.extend(await asyncio.to_thread(self.check_source_maps, ctx, root))
        return findings

    def _scan_tree(self, ctx: AgentContext, root: Path) -> list[Finding]:
        findings: list[Finding] = []
        for path in self._iter_source_files(root, ctx):
            findings.extend(self.scan_file(ctx, root, path))
        return findings

    def _iter_source_files(self, root: Path, ctx: AgentContext) -> list[Path]:
        """Return the source files to scan, skipping ``node_modules`` and anything over the size limit."""
        max_bytes = int(ctx.options.get("max_file_bytes", 2 * 1024 * 1024))  # type: ignore[call-overload]
        return [
            p
            for p in root.rglob("*")
            if p.suffix in self.SOURCE_SUFFIXES
            and "node_modules" not in p.parts
            and p.is_file()
            and p.stat().st_size <= max_bytes
        ]

    def scan_file(self, ctx: AgentContext, root: Path, path: Path) -> list[Finding]:
        """Apply every ``SinkRule`` to one file, line by line.

        Args:
            ctx: Agent context.
            root: Repository root, used to build relative ``file:line`` locations.
            path: File to scan.

        Returns:
            One finding per rule match.
        """
        out: list[Finding] = []
        text = path.read_text(encoding="utf-8", errors="ignore")
        for lineno, line in enumerate(text.splitlines(), start=1):
            for rule in self.rules:
                if rule.pattern.search(line):
                    out.append(
                        self.finding(
                            ctx,
                            title=rule.title,
                            severity=rule.severity,
                            cwe=rule.cwe,
                            location=f"{path.relative_to(root)}:{lineno}",
                            evidence=line.strip()[:300],
                            remediation=rule.remediation,
                        )
                    )
        return out

    async def audit_dependencies(self, ctx: AgentContext, root: Path) -> list[Finding]:
        """Run ``npm audit --json`` / OSV against the lockfile and map advisories to findings.

        TODO: Run the command in a subprocess with a timeout, with no shell and an argv list.
        Parse the JSON and map advisory severity to ``Severity``.
        """
        return []

    def check_source_maps(self, ctx: AgentContext, root: Path) -> list[Finding]:
        """Flag ``*.map`` files in production build output (CWE-540)."""
        out: list[Finding] = []
        for build_dir in ("dist", "build", ".next/static"):
            for m in (root / build_dir).rglob("*.map") if (root / build_dir).is_dir() else []:
                out.append(
                    self.finding(
                        ctx,
                        title="Source map shipped in production build",
                        severity=Severity.LOW,
                        cwe="CWE-540",
                        location=str(m.relative_to(root)),
                        remediation="Disable build.sourcemap in production or upload maps privately.",
                    )
                )
        return out
