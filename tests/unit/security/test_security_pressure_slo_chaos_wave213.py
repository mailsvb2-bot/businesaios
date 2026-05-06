from security.governance_owner_factory import build_security_governance_infrastructure


def test_pressure_monitor_slo_and_chaos_mode(tmp_path):
    owner = build_security_governance_infrastructure(base_dir=tmp_path, shared_secret='secret')
    for _ in range(6):
        owner.pressure_monitor.observe_baseline(revoke_count=0, quarantine_count=0, reencryption_backlog=0, approval_replay_count=0)
    owner.chaos_mode.simulate(event_kind='kms_failure', target_id='provider:aws-kms')
    owner.governance._incident_registry.open_incident(incident_kind='approval-replay-suspected', payload={'approval_id': 'a1'})
    snapshot = owner.pressure_monitor.snapshot()
    assert snapshot.approval_replay_anomaly.anomalous is True
    summary = owner.runtime_summary.build()
    slo = owner.slo_model.evaluate(rotation_backlog=summary.rotation_backlog, reencryption_backlog=summary.reencryption_backlog, open_incidents=summary.open_incidents, successful_drills=1, total_drills=1)
    assert slo.drill_success_rate_ok is True
    assert 'chaos:kms_failure' in summary.latest_anomaly_flags
