"""FastAPI application entry point."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Path, Query, Request
from fastapi.middleware.cors import CORSMiddleware

from secaudit.core.config import get_settings
from secaudit.db.MongoManager import MongoManager
from secaudit.models import Severity


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    mongo = MongoManager()
    await mongo.connect()
    await mongo.ensure_indexes()
    app.state.mongo = mongo
    yield
    await mongo.close()


settings = get_settings()
app = FastAPI(
    title="SecAudit API",
    lifespan=lifespan,
    docs_url="/docs" if settings.env != "prod" else None,
    redoc_url=None,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["Authorization", "Content-Type"],
)


@app.get("/healthz")
async def healthz() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/scans/{scan_id}/findings")
async def list_findings(
    request: Request,
    scan_id: str = Path(pattern=r"^[a-f0-9]{32}$"),
    severity: Severity | None = None,
    limit: int = Query(default=100, le=1000),
) -> list[dict[str, object]]:
    """Return findings for a scan.

    The filter is built only from validated, typed values, never from the raw request body.
    TODO: Add an auth dependency (JWT validation and an ownership check on the scan).
    """
    mongo: MongoManager = request.app.state.mongo
    filter_: dict[str, object] = {"scan_id": scan_id}
    if severity is not None:
        filter_["severity"] = severity.value
    docs = await mongo.find_safe("findings", filter_, limit=limit)
    for d in docs:
        d.pop("_id", None)
    return docs
