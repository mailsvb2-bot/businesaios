from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from execution.closed_loop_orchestrator import ClosedLoopOrchestrator
from execution.closed_loop_orchestrator_economic import build_economic_bundle_reconciliation
from execution.economic_audit_bundle import EconomicAuditBundleService
from runtime.execution.executor_observability import _generated_at_ms_from_env


class _IntBackendFailure:
    def __int__(self) -> int:
        raise OSError('clock backend unavailable')


class _Rows:
    def list_rows(self):
        return ()


class _Reconciliation:
    def to_dict(self) -> dict[str, object]:
        return {'consistent': True, 'metadata': {'quorum_failure_segments': []}}


class _ReconciliationBuilder:
    def build(self, **_kwargs) -> _Reconciliation:
        return _Reconciliation()


class _Forensics:
    def record_event(self, **_kwargs) -> None:
        return None


class _RestoreService:
    def __init__(self, error: Exception) -> None:
        self._error = error

    def restore_bundle(self, **_kwargs):
        raise self._error


class _Quarantine:
    def __init__(self) -> None:
        self.rows: list[object] = []

    def record(self, row: object) -> None:
        self.rows.append(row)


def _env(value: object) -> SimpleNamespace:
    return SimpleNamespace(decision=SimpleNamespace(payload={'generated_at_ms': value}))


def _bundle() -> dict[str, object]:
    return {
        'bundle_id': 'bundle-1',
        'digest': 'digest-1',
        'payload': {'export_manifest': {'scope': {'profile_name': 'standard'}}},
    }


def _helper_reconciliation(error: Exception) -> dict[str, object]:
    rows = _Rows()
    return build_economic_bundle_reconciliation(
        economic_audit_bundle_service=_RestoreService(error),
        economic_multi_backend_reconciliation=_ReconciliationBuilder(),
        economic_forensics_service=_Forensics(),
        economic_store_bundle=None,
        economic_memory_store=rows,
        roi_history_store=rows,
        economic_policy_snapshot_store=rows,
        economic_trace_store=rows,
        economic_metrics_store=rows,
        bundle=_bundle(),
        bundle_entry={'path': '/bundle.json'},
    )


def _orchestrator(error: Exception) -> ClosedLoopOrchestrator:
    rows = _Rows()
    orchestrator = object.__new__(ClosedLoopOrchestrator)
    orchestrator._economic_audit_bundle_service = _RestoreService(error)
    orchestrator._economic_multi_backend_reconciliation = _ReconciliationBuilder()
    orchestrator._economic_forensics_service = _Forensics()
    orchestrator._economic_store_bundle = None
    orchestrator._economic_memory_store = rows
    orchestrator._roi_history_store = rows
    orchestrator._economic_policy_snapshot_store = rows
    orchestrator._economic_trace_store = rows
    orchestrator._economic_metrics_store = rows
    return orchestrator


def test_observability_timestamp_tolerates_invalid_input() -> None:
    assert _generated_at_ms_from_env(env=_env('invalid'), safe_dict=dict) == 0


def test_observability_timestamp_does_not_hide_backend_failure() -> None:
    with pytest.raises(OSError, match='clock backend unavailable'):
        _generated_at_ms_from_env(env=_env(_IntBackendFailure()), safe_dict=dict)


def test_economic_bundle_parse_error_is_quarantined(tmp_path: Path) -> None:
    quarantine = _Quarantine()
    path = tmp_path / 'bundle.json'
    path.write_text('{broken json', encoding='utf-8')

    with pytest.raises(ValueError):
        EconomicAuditBundleService(quarantine_sink=quarantine).import_json(path=path)

    assert len(quarantine.rows) == 1


def test_economic_bundle_unexpected_reader_failure_is_visible(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    quarantine = _Quarantine()
    path = tmp_path / 'bundle.json'
    path.write_text('{}', encoding='utf-8')
    monkeypatch.setattr(Path, 'read_text', lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError('reader contract failed')))

    with pytest.raises(RuntimeError, match='reader contract failed'):
        EconomicAuditBundleService(quarantine_sink=quarantine).import_json(path=path)

    assert quarantine.rows == []


def test_helper_restore_validation_failure_becomes_invalid_import() -> None:
    result = _helper_reconciliation(ValueError('invalid restored bundle'))

    assert result['import_validation']['status'] == 'invalid'


def test_helper_restore_dependency_failure_is_visible() -> None:
    with pytest.raises(RuntimeError, match='restore backend unavailable'):
        _helper_reconciliation(RuntimeError('restore backend unavailable'))


def test_orchestrator_restore_validation_failure_becomes_invalid_import() -> None:
    result = _orchestrator(ValueError('invalid restored bundle'))._build_economic_bundle_reconciliation(
        bundle=_bundle(),
        bundle_entry={'path': '/bundle.json'},
    )

    assert result['import_validation']['status'] == 'invalid'


def test_orchestrator_restore_dependency_failure_is_visible() -> None:
    with pytest.raises(RuntimeError, match='restore backend unavailable'):
        _orchestrator(RuntimeError('restore backend unavailable'))._build_economic_bundle_reconciliation(
            bundle=_bundle(),
            bundle_entry={'path': '/bundle.json'},
        )
