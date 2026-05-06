from pathlib import Path


def test_change_management_is_separate() -> None:
    assert Path("infra/change_management.py").exists()
    assert Path("infra/change_request.py").exists()
