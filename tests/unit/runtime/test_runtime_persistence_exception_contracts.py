from __future__ import annotations

from types import SimpleNamespace

import pytest

from runtime.execution.correlation import extract_correlation_key
from runtime.execution.governance_audit_support import _append_governance_audit


class _FailingAuditLog:
    def append(self, event) -> None:
        raise OSError("audit storage unavailable")


class _SnapshotStore:
    def __init__(self, value=None, error: Exception | None = None) -> None:
        self._value = value
        self._error = error

    def get(self, snapshot_id: str):
        if self._error is not None:
            raise self._error
        return self._value


def test_governance_audit_persistence_failure_is_visible() -> None:
    executor = SimpleNamespace(_governance_audit_log=_FailingAuditLog())

    with pytest.raises(OSError, match="audit storage unavailable"):
        _append_governance_audit(
            executor=executor,
            tenant_id="tenant-1",
            event_type="governance_execution_approval_satisfied",
            payload={"decision_id": "decision-1"},
        )


def test_correlation_parser_tolerates_malformed_snapshot_only() -> None:
    assert extract_correlation_key(_SnapshotStore(b"not-json"), "snapshot-1") is None
    assert extract_correlation_key(_SnapshotStore(b"\xff"), "snapshot-1") is None


def test_correlation_snapshot_store_failure_is_visible() -> None:
    with pytest.raises(OSError, match="snapshot backend unavailable"):
        extract_correlation_key(
            _SnapshotStore(error=OSError("snapshot backend unavailable")),
            "snapshot-1",
        )
