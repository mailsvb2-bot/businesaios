from pathlib import Path


def test_kill_switches_are_separate() -> None:
    assert Path("infra/kill_switches.py").exists()
    assert Path("infra/maintenance_mode.py").exists()
