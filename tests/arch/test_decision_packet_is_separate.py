from pathlib import Path


def test_decision_packet_is_separate() -> None:
    assert Path("infra/decision_packet.py").exists()
    assert Path("infra/constitutional_evidence.py").exists()
