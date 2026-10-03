# CLAUDE.md

Project context for Claude Code. Keep this file current; it is loaded into every session.

## What this is

**SecAudit**: a multi-agent framework for automated security auditing and vulnerability scanning.
Specialised agents (frontend scanner, auth validator, database auditor) are coordinated by an
orchestrator. They write normalised `Finding` records to MongoDB, and a React dashboard shows the results.

**This is a defensive tool.** Agents may only target systems listed in an approved `ScanScope`
(an allowlist of hosts, repos and databases with a named owner and authorisation reference).
Never write code that scans, connects to or brute-forces a target outside the scope.

## Monorepo layout

```
frontend/            React 18 + Vite + TypeScript dashboard (port 5173)
backend/             Python 3.12 package `secaudit` (FastAPI API on port 8000)
  src/secaudit/
    agents/          BaseAgent + FrontendScannerAgent, AuthValidatorAgent, DatabaseAuditorAgent
    orchestrator/    Fans scan jobs out to agents and aggregates findings
    db/              MongoManager (the ONLY module that imports pymongo)
    models/          Pydantic models: Finding, ScanScope, ScanJob, Severity
    api/             FastAPI routers
    core/            Settings (pydantic-settings), logging, secret redaction
  tests/             pytest; unit/ needs no network, integration/ needs docker compose
mongo/               mongod.conf, init scripts (roles, users, schema validators)
infra/               docker-compose and deployment manifests
.claude/skills/      Audit playbooks: react-frontend-audit, python-backend-audit, mongodb-audit
```

## Commands

```bash
# Infrastructure
docker compose -f infra/docker-compose.yml up -d mongo       # local MongoDB with auth + TLS off (dev only)

# Backend (run from backend/)
uv sync                                                      # install deps into .venv
uv run uvicorn secaudit.api.main:app --reload --port 8000
uv run pytest tests/unit                                     # fast, no network
uv run pytest tests/integration                              # needs mongo running
uv run ruff check . && uv run ruff format --check .
uv run mypy src
uv run bandit -r src -c pyproject.toml
uv run pip-audit

# Frontend (run from frontend/)
npm ci
npm run dev
npm run lint && npm run typecheck
npm test
npm audit --omit=dev
```

## Engineering rules

1. **Scope first.** Every agent's `run()` checks `ScanScope.is_in_scope(target)` before any I/O.
   An out-of-scope target raises `OutOfScopeError`; the agent never skips it silently.
2. **No secrets in code, logs or findings.** Secrets come from env vars via `core.config.Settings`.
   Evidence goes through `core.redaction.redact()` before anything is persisted. Tokens are
   stored only as SHA-256 fingerprints.
3. **MongoDB access goes only through `MongoManager`.** No other module imports `pymongo`.
   Queries never build filters from raw user input; values are validated with Pydantic first,
   and operator keys (`$where`, `$function`, `$accumulator`) are rejected.
4. **Least privilege.** The app uses the `secaudit_app` role (readWrite on `secaudit` only).
   Auditing a *target* database uses a separate read-only credential supplied per scope.
5. **Findings are normalised.** Every agent returns `list[Finding]` with severity (CVSS-aligned),
   CWE id, location, evidence (redacted) and remediation text. Agents never invent new shapes.
6. **Agents are async and side-effect free** except for the `Finding`s they return.
   Network calls have timeouts and rate limits, and the payloads they send are non-destructive
   (no writes or deletes against target systems).
7. **Type everything.** `mypy --strict` must pass, and TypeScript runs with `strict: true`.
8. **Tests.** Every new check comes with a unit test that runs against a fixture
   (`tests/fixtures/`) and needs no live target.

## Conventions

- Python: ruff (line length 100), Google-style docstrings, `from __future__ import annotations`.
- Agent modules use PascalCase filenames that match their class (`FrontendScannerAgent.py`);
  all other modules are snake_case.
- React: function components and hooks only. Server state lives in TanStack Query, and the
  frontend never uses `dangerouslySetInnerHTML`.
- Commits: Conventional Commits (`feat(agents): ...`, `fix(db): ...`).

## Skills

When performing an audit, load the matching skill and follow its steps in order:
- `react-frontend-audit`: client-side code, bundles, dependencies, CSP and storage
- `python-backend-audit`: API, auth, injection, deserialisation, dependencies
- `mongodb-audit`: connection security, RBAC, NoSQL injection, PCI data partitioning
