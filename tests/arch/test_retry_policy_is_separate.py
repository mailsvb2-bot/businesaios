from pathlib import Path


def test_retry_policy_is_separate() -> None:
    assert Path("infra/retry_policy.py").exists()
    assert Path("infra/retry_models.py").exists()
