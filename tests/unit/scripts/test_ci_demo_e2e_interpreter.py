from __future__ import annotations

import sys

from scripts.ci import step_demo_e2e_smoke as step
from scripts.ci.subprocess_io import CommandOutcome


def test_demo_e2e_uses_the_active_ci_interpreter(monkeypatch, tmp_path) -> None:
    captured: dict[str, object] = {}

    def fake_run_command(command, *, env=None, timeout=None, **kwargs):
        captured["command"] = list(command)
        captured["env"] = dict(env or {})
        captured["timeout"] = timeout
        return CommandOutcome(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(step, "_CI_DEMO_STATE_ROOT", tmp_path / "state")
    monkeypatch.setattr(step, "_CI_DEMO_TENANCY_DIR", tmp_path / "state" / "tenancy")
    monkeypatch.setattr(step, "_CI_DEMO_DATA_DIR", tmp_path / "state" / "data")
    monkeypatch.setattr(step, "cleanup_ci_runtime_state", lambda: [])
    monkeypatch.setattr(step, "run_command", fake_run_command)

    ok, message = step.run()

    assert ok is True
    assert message == "demo e2e smoke passed"
    assert captured["command"] == [sys.executable, "main.py"]
    assert captured["timeout"] == 180
    assert captured["env"]["DATA_DIR"] == str(tmp_path / "state" / "data")
