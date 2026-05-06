from pathlib import Path


def test_approval_flow_is_separate() -> None:
    assert Path("infra/approval_service.py").exists()
    assert Path("infra/multi_step_approvals.py").exists()
