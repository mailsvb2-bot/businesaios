from pathlib import Path


def test_governance_evidence_layer_is_split() -> None:
    for rel in (
        "infra/governance_evidence.py",
        "infra/approval_evidence_links.py",
        "infra/policy_snapshot_evidence.py",
        "infra/constitutional_evidence.py",
        "infra/decision_packet.py",
        "infra/rollback_packet.py",
        "infra/operator_session_records.py",
        "infra/governance_evidence_service.py",
        "infra/governance_evidence_boot.py",
        "infra/governance_evidence_boot_result.py",
    ):
        assert Path(rel).exists(), rel
