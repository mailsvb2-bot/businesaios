from pathlib import Path


def test_graceful_shutdown_is_separate() -> None:
    assert Path("infra/graceful_shutdown.py").exists()
    assert Path("infra/shutdown_hooks.py").exists()
