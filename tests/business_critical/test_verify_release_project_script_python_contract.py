from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import scripts.ci.step_verify_release as verify_release_step


def test_verify_release_project_script_receives_canonical_python(monkeypatch, tmp_path) -> None:
    script = tmp_path / "scripts" / "verify_release.sh"
    script.parent.mkdir(parents=True)
    script.write_text("#!/usr/bin/env bash\n", encoding="utf-8")
    calls: list[tuple[list[str], dict[str, str]]] = []

    monkeypatch.setattr(verify_release_step, "repo_root", lambda: tmp_path)

    def fake_run_command(command, *, env=None, **_kwargs):
        calls.append((list(command), dict(env or {})))
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(verify_release_step, "run_command", fake_run_command)

    ok, message = verify_release_step._run_optional_project_release_script()

    assert ok is True, message
    assert calls == [(["bash", str(script)], {"PYTHON_BIN": sys.executable})]
