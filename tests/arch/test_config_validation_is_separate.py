from pathlib import Path


def test_config_validation_is_separate() -> None:
    assert Path("config/validation.py").exists()
