"""Agent that audits access tokens and API endpoints for unauthorised access.

Playbook: ``.claude/skills/python-backend-audit/SKILL.md`` (sections 3-4).
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import ClassVar, Literal

import httpx
import jwt

from secaudit.agents.base_agent import AgentContext, BaseAgent
from secaudit.core.config import get_settings
from secaudit.core.redaction import fingerprint
from secaudit.models import Finding, Severity, TargetKind

HttpMethod = Literal["GET", "HEAD", "OPTIONS", "POST", "PUT", "PATCH", "DELETE"]
SAFE_METHODS: frozenset[str] = frozenset({"GET", "HEAD", "OPTIONS"})


@dataclass(frozen=True, slots=True)
class TestPrincipal:
    """A test identity supplied with the scope. Its token is never logged; only the fingerprint is.

    Attributes:
        label: For example ``"user_a"``, ``"user_b"``, ``"admin"``, ``"anonymous"``.
        role: Logical role used to build the expected access matrix.
        token: Bearer token, or ``None`` for anonymous.
    """

    label: str
    role: str
    token: str | None = field(repr=False)

    @property
    def token_id(self) -> str:
        return fingerprint(self.token) if self.token else "anonymous"


@dataclass(frozen=True, slots=True)
class EndpointSpec:
    """One API operation and which roles should be allowed to call it.

    Attributes:
        method: HTTP method. Unsafe methods are skipped unless explicitly enabled.
        path: Path template, for example ``/api/orders/{order_id}``.
        allowed_roles: Roles expected to receive 2xx.
        owner_param: Name of the path param identifying a user-owned object (for BOLA tests).
    """

    method: HttpMethod
    path: str
    allowed_roles: frozenset[str]
    owner_param: str | None = None


@dataclass(slots=True)
class AccessResult:
    endpoint: EndpointSpec
    principal: str
    expected_allowed: bool
    status_code: int

    @property
    def violated(self) -> bool:
        """True if a principal that should be denied got a 2xx response."""
        return not self.expected_allowed and 200 <= self.status_code < 300


class AuthValidatorAgent(BaseAgent):
    """Validates JWT hygiene and enforces an endpoint x role access matrix.

    Scope kind: ``TargetKind.URL``. Requires ``scope.allow_dynamic``.

    Checks:
        * **Token analysis** (offline): algorithm, ``exp``/``nbf``/``iss``/``aud`` presence,
          excessive lifetime, sensitive claims in the payload.
        * **Authentication**: protected endpoints reject missing, expired, malformed and
          ``alg: none`` tokens with 401.
        * **Authorisation (BFLA)**: each principal is checked against each endpoint's ``allowed_roles``.
        * **Object-level (BOLA/IDOR)**: principal A requests objects owned by principal B.

    Safety:
        Only ``SAFE_METHODS`` run unless ``ctx.options["allow_unsafe_methods"]`` is True.
        Requests are rate-limited by ``Settings.max_requests_per_second``.

    Options:
        principals (list[TestPrincipal]): Test identities (required).
        endpoints (list[EndpointSpec]): Endpoints to test. If omitted, discovered from ``/openapi.json``.
        object_ids (dict[str, str]): Maps principal label to an object id that principal owns.
    """

    name: ClassVar[str] = "auth_validator"
    target_kind: ClassVar[TargetKind] = TargetKind.URL
    requires_dynamic: ClassVar[bool] = True

    MAX_TOKEN_LIFETIME_S: ClassVar[int] = 60 * 60

    def __init__(self, client: httpx.AsyncClient | None = None) -> None:
        super().__init__()
        settings = get_settings()
        self._client = client or httpx.AsyncClient(
            timeout=settings.http_timeout_s, follow_redirects=False
        )
        self._min_interval = 1.0 / settings.max_requests_per_second

    async def _execute(self, ctx: AgentContext) -> list[Finding]:
        principals: list[TestPrincipal] = list(ctx.options.get("principals", []))  # type: ignore[call-overload]
        endpoints: list[EndpointSpec] = list(
            ctx.options.get("endpoints", [])
        ) or await self.discover_endpoints(ctx)  # type: ignore[call-overload]

        findings: list[Finding] = []
        for p in principals:
            if p.token:
                findings.extend(self.analyse_token(ctx, p))
        findings.extend(await self.test_authentication(ctx, endpoints))
        results = await self.build_access_matrix(ctx, endpoints, principals)
        findings.extend(self._matrix_to_findings(ctx, results))
        return findings

    async def discover_endpoints(self, ctx: AgentContext) -> list[EndpointSpec]:
        """Fetch ``{target}/openapi.json`` and turn operations into ``EndpointSpec``s.

        TODO: Infer ``allowed_roles`` from security schemes or ``x-roles`` extensions. Fall back to
        "authenticated only".
        """
        return []

    def analyse_token(self, ctx: AgentContext, principal: TestPrincipal) -> list[Finding]:
        """Decode the token *without* trusting it and flag weak configuration.

        Signature verification is deliberately skipped: this inspects the token's structure,
        it does not authenticate it.
        """
        if principal.token is None:
            return []
        out: list[Finding] = []
        header = jwt.get_unverified_header(principal.token)
        claims = jwt.decode(principal.token, options={"verify_signature": False})
        loc = f"token:{principal.token_id}"

        if header.get("alg", "").lower() in {"none", ""}:
            out.append(
                self.finding(
                    ctx,
                    title="JWT uses alg=none",
                    severity=Severity.CRITICAL,
                    cwe="CWE-347",
                    location=loc,
                    remediation="Pin accepted algorithms server-side (e.g. RS256).",
                )
            )
        for claim in ("exp", "iss", "aud"):
            if claim not in claims:
                out.append(
                    self.finding(
                        ctx,
                        title=f"JWT missing '{claim}' claim",
                        severity=Severity.MEDIUM,
                        cwe="CWE-613" if claim == "exp" else "CWE-345",
                        location=loc,
                        remediation=f"Issue and validate the '{claim}' claim.",
                    )
                )
        if (
            "exp" in claims
            and "iat" in claims
            and claims["exp"] - claims["iat"] > self.MAX_TOKEN_LIFETIME_S
        ):
            out.append(
                self.finding(
                    ctx,
                    title="Long-lived access token",
                    severity=Severity.LOW,
                    cwe="CWE-613",
                    location=loc,
                    evidence=f"lifetime={claims['exp'] - claims['iat']}s",
                    remediation="Keep access tokens ≤ 1h and use refresh-token rotation.",
                )
            )
        return out

    async def test_authentication(
        self, ctx: AgentContext, endpoints: list[EndpointSpec]
    ) -> list[Finding]:
        """Send missing, malformed and ``alg: none`` tokens to protected endpoints. Expect 401 for each.

        TODO: Implement the negative-token cases. Reuse ``_request``.
        """
        return []

    async def build_access_matrix(
        self, ctx: AgentContext, endpoints: list[EndpointSpec], principals: list[TestPrincipal]
    ) -> list[AccessResult]:
        """Call each (endpoint, principal) pair and record the status code.

        Unsafe methods are skipped unless ``allow_unsafe_methods`` is set in options.
        """
        allow_unsafe = bool(ctx.options.get("allow_unsafe_methods", False))
        results: list[AccessResult] = []
        for ep in endpoints:
            if ep.method not in SAFE_METHODS and not allow_unsafe:
                continue
            for p in principals:
                status = await self._request(ctx, ep.method, self._render_path(ctx, ep, p), p)
                results.append(AccessResult(ep, p.label, p.role in ep.allowed_roles, status))
        return results

    def _render_path(self, ctx: AgentContext, ep: EndpointSpec, principal: TestPrincipal) -> str:
        """Fill path params. For BOLA, substitute an object owned by a *different* principal.

        TODO: Pick a foreign object id from ``ctx.options["object_ids"]``.
        """
        return ep.path

    async def _request(self, ctx: AgentContext, method: str, path: str, p: TestPrincipal) -> int:
        """Send a single rate-limited request. Returns the status code (0 on transport error)."""
        headers = {"Authorization": f"Bearer {p.token}"} if p.token else {}
        url = ctx.target.rstrip("/") + path
        ctx.scope.require(TargetKind.URL, url)  # re-check after path rendering
        await asyncio.sleep(self._min_interval)
        try:
            resp = await self._client.request(method, url, headers=headers)
        except httpx.HTTPError as exc:
            self.log.warning("request failed %s %s: %s", method, path, type(exc).__name__)
            return 0
        return resp.status_code

    def _matrix_to_findings(self, ctx: AgentContext, results: list[AccessResult]) -> list[Finding]:
        return [
            self.finding(
                ctx,
                title=f"Unauthorised access: {r.principal} → {r.endpoint.method} {r.endpoint.path}",
                severity=Severity.HIGH,
                cwe="CWE-639" if r.endpoint.owner_param else "CWE-285",
                location=f"{r.endpoint.method} {r.endpoint.path}",
                evidence=f"status={r.status_code} expected=deny",
                remediation="Enforce role and ownership checks server-side in the route dependency.",
            )
            for r in results
            if r.violated
        ]
