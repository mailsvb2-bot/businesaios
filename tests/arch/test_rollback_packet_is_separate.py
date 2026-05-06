from pathlib import Path


def test_rollback_packet_is_separate() -> None:
    assert Path("infra/rollback_packet.py").exists()
    assert Path("infra/policy_snapshot_evidence.py").exists()
