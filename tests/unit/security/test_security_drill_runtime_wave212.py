import time

from security.governance_owner_factory import build_security_governance_infrastructure
from security.security_drill_schedule_store import SecurityDrillSchedule


def test_security_drill_runtime_runs_due_schedule_and_reschedules(tmp_path):
    owner = build_security_governance_infrastructure(base_dir=tmp_path, shared_secret='secret')
    now = int(time.time())
    owner.drill_runtime.schedule(SecurityDrillSchedule(
        drill_id='drill-1',
        drill_kind='token_quarantine_recovery',
        actor='secops',
        target_entity_id='tok-drill',
        interval_seconds=60,
        next_run_epoch_s=now - 1,
    ))
    outcomes = owner.drill_runtime.run_due(now_epoch_s=now)
    assert len(outcomes) == 1
    assert outcomes[0].success is True
    enabled = owner.drill_runtime._schedule_store.list_enabled()
    assert enabled[0].next_run_epoch_s >= now + 60
