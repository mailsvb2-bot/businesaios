from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import scripts.ci.step_verify_release as verify_release_step


def test_verify_release_make_targets_receive_canonical_python(monkeypatch) -> None:
    calls: list[tuple[list[str], dict[str, str]]] = []

    monkeypatch.setattr(verify_release_step, "has_make_target", lambda _name: True)

    def fake_run_command(command, *, env=None, **_kwargs):
        calls.append((list(command), dict(env or {})))
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(verify_release_step, "run_command", fake_run_command)

    ok, message = verify_release_step._run_optional_make_target("ci-locks")

    assert ok is True, message
    assert calls == [(["make", "ci-locks"], {"PYTHON_BIN": sys.executable})]


def test_release_shell_helpers_use_propagated_python() -> None:
    root = Path(__file__).resolve().parents[2]
    locks = (root / "ci" / "check_locks.sh").read_text(encoding="utf-8")
    verifier = (root / "scripts" / "verify_release.sh").read_text(encoding="utf-8")

    assert 'PYTHON_BIN="${PYTHON_BIN:-python}"' in locks
    assert '"$PYTHON_BIN" -m pytest "${PYTEST_ARGS[@]}"' in locks
    assert 'PYTHON_BIN="${PYTHON_BIN:-python}"' in verifier
    assert '"$PYTHON_BIN" -m scripts.ci.cli --gate fast' in verifier
