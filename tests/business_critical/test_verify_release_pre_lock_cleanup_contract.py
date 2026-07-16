from __future__ import annotations

import scripts.ci.step_verify_release as verify_release_step


def test_verify_release_cleans_runtime_state_before_ci_locks(monkeypatch) -> None:
    events: list[str] = []

    def fake_make_target(name: str) -> tuple[bool, str]:
        events.append(name)
        return True, f"passed:{name}"

    def fake_cleanup() -> list[str]:
        events.append("cleanup")
        return ["data/runtime/generated.sqlite3"]

    monkeypatch.setattr(verify_release_step, "_run_optional_make_target", fake_make_target)
    monkeypatch.setattr(verify_release_step, "cleanup_ci_runtime_state", fake_cleanup)
    monkeypatch.setattr(
        verify_release_step,
        "_run_optional_project_release_script",
        lambda: (True, "project:passed"),
    )
    monkeypatch.setattr(
        verify_release_step,
        "_aggregate_required_proof_artifacts",
        lambda: (True, "proof:ready"),
    )

    ok, message = verify_release_step.run()

    assert ok is True, message
    assert events == ["ci-guard", "cleanup", "ci-locks"]
    assert "pre-ci-lock runtime cleanup removed 1 mutable runtime artifact(s)" in message


def test_verify_release_blocks_when_pre_lock_cleanup_fails(monkeypatch) -> None:
    events: list[str] = []

    def fake_make_target(name: str) -> tuple[bool, str]:
        events.append(name)
        return True, f"passed:{name}"

    def failing_cleanup() -> list[str]:
        events.append("cleanup")
        raise OSError("cannot remove runtime state")

    monkeypatch.setattr(verify_release_step, "_run_optional_make_target", fake_make_target)
    monkeypatch.setattr(verify_release_step, "cleanup_ci_runtime_state", failing_cleanup)

    ok, message = verify_release_step.run()

    assert ok is False
    assert events == ["ci-guard", "cleanup"]
    assert "pre-ci-lock runtime cleanup failed: OSError" in message
