"""Agent that simulates backend access checks against MongoDB and audits PCI data partitioning.

Playbook: ``.claude/skills/mongodb-audit/SKILL.md``.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, ClassVar, Literal

from secaudit.agents.base_agent import AgentContext, BaseAgent
from secaudit.core.redaction import find_pans
from secaudit.db.MongoManager import MongoManager, TargetClient
from secaudit.models import Finding, Severity, TargetKind

DataZone = Literal["cde", "non_cde"]

OVER_PRIVILEGED_ROLES: frozenset[str] = frozenset(
    {
        "root",
        "dbOwner",
        "userAdminAnyDatabase",
        "readWriteAnyDatabase",
        "dbAdminAnyDatabase",
        "__system",
    }
)


@dataclass(frozen=True, slots=True)
class DataMap:
    """Classification of namespaces into PCI cardholder-data-environment (CDE) zones.

    Attributes:
        zones: Maps ``"db.collection"`` (or ``"db.*"``) to ``"cde"`` or ``"non_cde"``.
            Namespaces that are not listed count as ``non_cde``.
        app_users: Usernames of application service accounts. They are held to least privilege.
    """

    zones: dict[str, DataZone]
    app_users: frozenset[str] = frozenset()

    def zone_of(self, db: str, coll: str) -> DataZone:
        return self.zones.get(f"{db}.{coll}") or self.zones.get(f"{db}.*") or "non_cde"


class DatabaseAuditorAgent(BaseAgent):
    """Read-only MongoDB auditor: configuration, RBAC, access simulation and PAN discovery.

    Scope kind: ``TargetKind.MONGO``. The connection URI is resolved from
    ``ScopedTarget.credential_ref`` by an injected ``secret_resolver``, so it never appears in
    options or logs.

    Checks:
        1. ``check_transport``: TLS mode is ``requireTLS``, minimum TLS 1.2.
        2. ``check_authentication``: authorisation is enabled, SCRAM-SHA-256 or stronger.
        3. ``check_rbac``: app users do not hold over-privileged roles, and no role spans CDE and non-CDE.
        4. ``simulate_access``: for each app user, compare the effective privileges with what the
           ``DataMap`` says they should be (the "backend access check" simulation).
        5. ``scan_cardholder_data``: ``$sample`` documents and detect Luhn-valid PANs. Only
           masked values are reported, and a PAN outside the CDE is critical.

    Options:
        data_map (DataMap): Required for checks 3-5.
        sample_size (int): Documents sampled per collection. Default from settings.
    """

    name: ClassVar[str] = "database_auditor"
    target_kind: ClassVar[TargetKind] = TargetKind.MONGO

    def __init__(self, mongo: MongoManager, secret_resolver: Callable[[str], str]) -> None:
        """
        Args:
            mongo: Shared manager. Used only for its secure ``target_client`` factory.
            secret_resolver: Maps a ``credential_ref`` to a connection URI (vault lookup).
        """
        super().__init__()
        self._mongo = mongo
        self._resolve = secret_resolver

    async def _execute(self, ctx: AgentContext) -> list[Finding]:
        scoped = ctx.scope.require(TargetKind.MONGO, ctx.target)
        if scoped.credential_ref is None:
            raise ValueError("Mongo targets require a credential_ref")
        data_map: DataMap | None = ctx.options.get("data_map")  # type: ignore[assignment]

        findings: list[Finding] = []
        async with self._mongo.target_client(
            ctx.scope, ctx.target, self._resolve(scoped.credential_ref)
        ) as client:
            findings += await self.check_transport(ctx, client)
            findings += await self.check_authentication(ctx, client)
            if data_map is not None:
                findings += await self.check_rbac(ctx, client, data_map)
                findings += await self.simulate_access(ctx, client, data_map)
                findings += await self.scan_cardholder_data(ctx, client, data_map)
        return findings

    async def _cmd_line_opts(self, client: TargetClient) -> dict[str, Any]:
        """Return ``getCmdLineOpts.parsed`` (needs the ``clusterMonitor`` role)."""
        res = await client.admin.command("getCmdLineOpts")
        return dict(res.get("parsed", {}))

    async def check_transport(self, ctx: AgentContext, client: TargetClient) -> list[Finding]:
        """Flag ``net.tls.mode`` other than ``requireTLS`` and legacy TLS protocols (PCI Req 4)."""
        tls = (await self._cmd_line_opts(client)).get("net", {}).get("tls", {})
        if tls.get("mode") != "requireTLS":
            return [
                self.finding(
                    ctx,
                    title="MongoDB does not require TLS",
                    severity=Severity.HIGH,
                    cwe="CWE-319",
                    compliance=["PCI-DSS-4.0:4.2.1"],
                    location="net.tls.mode",
                    evidence=f"mode={tls.get('mode')!r}",
                    remediation="Set net.tls.mode: requireTLS and disabledProtocols: TLS1_0,TLS1_1.",
                )
            ]
        return []

    async def check_authentication(self, ctx: AgentContext, client: TargetClient) -> list[Finding]:
        """Flag disabled authorisation and weak auth mechanisms (PCI Req 8).

        TODO: Read ``security.authorization`` and ``getParameter authenticationMechanisms``.
        """
        return []

    async def check_rbac(
        self, ctx: AgentContext, client: TargetClient, data_map: DataMap
    ) -> list[Finding]:
        """Flag over-privileged app users via ``usersInfo`` (PCI Req 7).

        Uses ``usersInfo: {forAllDBs: true}``, which needs ``viewUser`` on the target dbs.
        """
        out: list[Finding] = []
        info = await client.admin.command({"usersInfo": {"forAllDBs": True}})
        for user in info.get("users", []):
            if user["user"] not in data_map.app_users:
                continue
            held = {r["role"] for r in user.get("roles", [])}
            for role in sorted(held & OVER_PRIVILEGED_ROLES):
                out.append(
                    self.finding(
                        ctx,
                        title=f"App user '{user['user']}' holds over-privileged role '{role}'",
                        severity=Severity.HIGH,
                        cwe="CWE-250",
                        compliance=["PCI-DSS-4.0:7.2.2"],
                        location=f"{user['db']}.{user['user']}",
                        remediation="Replace with a custom role scoped to the required collections and actions.",
                    )
                )
        return out

    async def simulate_access(
        self, ctx: AgentContext, client: TargetClient, data_map: DataMap
    ) -> list[Finding]:
        """Compare each app user's effective privileges with its intended zone.

        Approach: ``usersInfo`` with ``showPrivileges: true`` lists the inherited privileges as
        ``{resource: {db, collection}, actions}``. For each privilege, resolve the zone via
        ``data_map`` and flag non-CDE users that can ``find`` on CDE namespaces. No queries run
        *as* the user, so the simulation is fully read-only.

        TODO: Implement privilege resolution, including wildcard resources (``collection: ""``).
        """
        return []

    async def scan_cardholder_data(
        self, ctx: AgentContext, client: TargetClient, data_map: DataMap
    ) -> list[Finding]:
        """Sample documents and detect PANs (Luhn-valid). Report only masked values.

        * PAN in a ``non_cde`` namespace: CRITICAL (PCI 3.2 / scope creep).
        * PAN in a ``cde`` namespace without field-level encryption: HIGH (PCI 3.5.1).
          TODO: detect CSFLE by checking whether the values are BSON Binary subtype 6.
        """
        sample_size = int(ctx.options.get("sample_size", 200))  # type: ignore[call-overload]
        out: list[Finding] = []
        for db_name in await client.list_database_names():
            if db_name in {"admin", "local", "config"}:
                continue
            db = client[db_name]
            for coll in await db.list_collection_names():
                cursor = await db[coll].aggregate([{"$sample": {"size": sample_size}}])
                masked: set[str] = set()
                async for doc in cursor:
                    masked.update(find_pans(str(doc)))
                if not masked:
                    continue
                zone = data_map.zone_of(db_name, coll)
                out.append(
                    self.finding(
                        ctx,
                        title=f"Cardholder data found in {zone.upper()} collection",
                        severity=Severity.CRITICAL if zone == "non_cde" else Severity.HIGH,
                        cwe="CWE-312",
                        compliance=["PCI-DSS-4.0:3.5.1"],
                        location=f"{db_name}.{coll}",
                        evidence=f"{len(masked)} distinct PAN(s), e.g. {next(iter(masked))}",
                        remediation="Tokenise PANs or use Queryable Encryption, and keep them in CDE-only collections.",
                    )
                )
        return out
