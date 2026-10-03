from datetime import UTC, datetime, timedelta

import pytest

from secaudit.core.redaction import find_pans, redact
from secaudit.db.MongoManager import UnsafeQueryError, assert_safe_filter
from secaudit.models import ScanScope, TargetKind
from secaudit.models.scope import ScopedTarget


def _scope(*targets: ScopedTarget, expires_in: timedelta = timedelta(hours=1)) -> ScanScope:
    return ScanScope(
        owner="appsec",
        authorization_ref="SEC-123",
        targets=list(targets),
        expires_at=datetime.now(UTC) + expires_in,
    )


def test_scope_allows_listed_url_and_subpaths() -> None:
    s = _scope(ScopedTarget(kind=TargetKind.URL, identifier="https://app.example.com"))
    assert s.is_in_scope(TargetKind.URL, "https://app.example.com/api/orders")


def test_scope_rejects_lookalike_host_and_db_prefix() -> None:
    s = _scope(
        ScopedTarget(kind=TargetKind.URL, identifier="https://app.example.com"),
        ScopedTarget(kind=TargetKind.MONGO, identifier="db.internal:27017/payments"),
    )
    assert not s.is_in_scope(TargetKind.URL, "https://app.example.com.evil.io/")
    assert not s.is_in_scope(TargetKind.MONGO, "db.internal:27017/payments_archive")


def test_expired_scope_rejects_everything() -> None:
    s = _scope(ScopedTarget(kind=TargetKind.REPO, identifier="/src/app"), expires_in=timedelta(0))
    assert not s.is_in_scope(TargetKind.REPO, "/src/app")


def test_redact_masks_pan_and_credentials() -> None:
    out = redact("mongodb://admin:hunter2@db:27017 card=4111 1111 1111 1111")
    assert "hunter2" not in out
    assert "411111******1111" in out


def test_find_pans_ignores_non_luhn() -> None:
    assert find_pans("order 1234567890123") == []
    assert find_pans("4111111111111111") == ["411111******1111"]


def test_forbidden_mongo_operator_rejected() -> None:
    with pytest.raises(UnsafeQueryError):
        assert_safe_filter({"$or": [{"a": 1}, {"$where": "sleep(1000)"}]})
