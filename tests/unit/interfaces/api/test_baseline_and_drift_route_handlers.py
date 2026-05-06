from __future__ import annotations

from pathlib import Path

from execution.headless_ledger import FileHeadlessLedger, LedgerRecord
from interfaces.api.baseline_models import PromoteBaselineRequest, SelectBaselineRequest
from interfaces.api.baseline_route_handlers import BaselineRouteHandlers
from interfaces.api.drift_models import DriftAuditRequest, RollbackBaselineRequest
from interfaces.api.drift_route_handlers import DriftRouteHandlers


def _seed_run(tmp_path: Path, *, run_id: str, goal_score: float) -> None:
    ledger = FileHeadlessLedger(root_dir=tmp_path / '.runtime' / 'headless_ledger')
    ledger.write(
        LedgerRecord(
            run_id=run_id,
            trace_id=f'trace-{run_id}',
            business_id='biz-1',
            tenant_id='tenant-1',
            goal='grow revenue',
            completed=True,
            stop_reason='goal_reached',
            steps_count=2,
            final_feedback={'goal_score': goal_score},
            trace={'steps': []},
        )
    )


def test_baseline_route_handlers_aliases_delegate_to_canonical_governance_path(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    _seed_run(tmp_path, run_id='run-1', goal_score=0.8)
    _seed_run(tmp_path, run_id='run-2', goal_score=0.5)
    handlers = BaselineRouteHandlers.build_default()

    promoted = handlers.promote(PromoteBaselineRequest(baseline_name='b1', run_id='run-1', label='manual'))
    promoted_2 = handlers.handle_promote_baseline(PromoteBaselineRequest(baseline_name='b1', run_id='run-1', label='manual-2'))
    selected = handlers.select_baseline(SelectBaselineRequest(run_ids=['run-1', 'run-2']))
    selected_2 = handlers.handle_select_baseline(SelectBaselineRequest(run_ids=['run-1', 'run-2']))

    assert promoted.baseline_name == 'b1'
    assert promoted.source_run_id == 'run-1'
    assert promoted_2.baseline_name == 'b1'
    assert selected.selected_run_id == 'run-1'
    assert selected_2.selected_run_id == 'run-1'


def test_drift_route_handlers_aliases_delegate_to_canonical_governance_path(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    _seed_run(tmp_path, run_id='run-2', goal_score=0.9)
    baseline_handlers = BaselineRouteHandlers.build_default()
    baseline_handlers.promote_baseline(PromoteBaselineRequest(baseline_name='b2', run_id='run-2', label='manual'))

    handlers = DriftRouteHandlers.build_default()
    drift = handlers.audit(DriftAuditRequest(baseline_name='b2', candidate_run_id='run-2'))
    rollback = handlers.handle_rollback_baseline(
        RollbackBaselineRequest(baseline_name='b2', fallback_run_id='run-2', reason='manual_guardrail')
    )

    assert isinstance(drift.report_text, str)
    assert rollback.baseline_name == 'b2'
    assert rollback.source_run_id == 'run-2'
