from pathlib import Path


def test_feature_flags_are_separate() -> None:
    assert Path("infra/feature_flags.py").exists()
    assert Path("infra/feature_flag_store.py").exists()
