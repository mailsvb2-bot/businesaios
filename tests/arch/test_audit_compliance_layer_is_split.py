from pathlib import Path


def test_audit_compliance_layer_is_split() -> None:
    for rel in (
        "infra/audit_event.py",
        "infra/audit_sink.py",
        "infra/audit_log_service.py",
        "infra/change_management.py",
        "infra/change_request.py",
        "infra/operator_actions.py",
        "infra/policy_snapshots.py",
        "infra/incident_mode.py",
        "infra/compliance_boot.py",
        "infra/compliance_boot_result.py",
    ):
        assert Path(rel).exists(), rel
