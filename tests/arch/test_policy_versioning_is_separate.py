from pathlib import Path


def test_policy_versioning_is_separate() -> None:
    assert Path("infra/policy_versioning.py").exists()
    assert Path("infra/release_promotion.py").exists()
