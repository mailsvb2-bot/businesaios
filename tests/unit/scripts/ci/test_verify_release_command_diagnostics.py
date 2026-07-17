from __future__ import annotations

import json

from scripts.ci import step_verify_release
from scripts.ci.subprocess_io import CommandOutcome


def _patch_artifact_root(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(step_verify_release, "repo_root", lambda: tmp_path)
    monkeypatch.setattr(
        step_verify_release,
        "_artifact_path",
        lambda name: tmp_path / "artifacts" / "ci" / name,
    )


def test_failed_make_target_persists_diagnostic_output(tmp_path, monkeypatch) -> None:
    _patch_artifact_root(monkeypatch, tmp_path)
    monkeypatch.setattr(step_verify_release, "has_make_target", lambda _name: True)
    monkeypatch.setattr(
        step_verify_release,
        "run_command",
        lambda *_args, **_kwargs: CommandOutcome(
            returncode=3,
            stdout="collected 11 items\nFAILED tests/lock/test_example.py::test_lock\n",
            stderr="assertion detail\n",
        ),
    )

    ok, message = step_verify_release._run_optional_make_target("ci-locks")

    assert ok is False
    assert "make target ci-locks failed (exit=3)" in message
    assert "diagnostics=artifacts/ci/verify_release_command_failure.json" in message

    payload = json.loads(
        (tmp_path / "artifacts" / "ci" / "verify_release_command_failure.json").read_text(
            encoding="utf-8"
        )
    )
    assert payload["status"] == "failed"
    assert payload["label"] == "make target ci-locks"
    assert payload["command"] == ["make", "ci-locks"]
    assert payload["returncode"] == 3
    assert "FAILED tests/lock/test_example.py::test_lock" in payload["stdout_tail"]
    assert payload["stderr_tail"] == "assertion detail"
    assert payload["claims_production_ready"] is False


def test_clear_command_failure_artifact_removes_stale_evidence(
    tmp_path,
    monkeypatch,
) -> None:
    _patch_artifact_root(monkeypatch, tmp_path)
    stale = tmp_path / "artifacts" / "ci" / "verify_release_command_failure.json"
    stale.parent.mkdir(parents=True)
    stale.write_text('{"status":"failed"}\n', encoding="utf-8")

    step_verify_release._clear_command_failure_artifact()

    assert not stale.exists()
