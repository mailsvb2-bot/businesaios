from __future__ import annotations

from scripts.ci import regression_impact_hardened
from scripts.ci import step_ids
from scripts.ci import step_doctor
from scripts.ci import step_registry
from scripts.ci import step_regression_impact
from scripts.ci.plan_registry import plan_for_gate
from scripts.ci.regression_impact import (
    IMPACT_RULES,
    blocked_artifact_paths,
    impacted_rules,
    missing_fast_steps_for_paths,
    required_fast_steps_for_paths,
)
from scripts.ci.subprocess_io import CommandOutcome


def _fast_steps() -> tuple[str, ...]:
    return tuple(step.name for step in plan_for_gate("fast").steps)


def test_regression_impact_step_is_registered_and_in_fast_gate() -> None:
    assert step_ids.regression_impact() == "regression-impact"
    assert "regression-impact" in step_registry.all_step_names()
    assert "regression-impact" in _fast_steps()


def test_all_impact_rules_are_covered_by_fast_gate() -> None:
    fast_steps = _fast_steps()
    for rule in IMPACT_RULES:
        assert not missing_fast_steps_for_paths((rule.prefixes[0] + "changed.py",), fast_steps)


def test_runtime_change_requires_runtime_regression_checks() -> None:
    required = required_fast_steps_for_paths(("runtime/boot/actions_registry.py",))
    assert "boot-smoke" in required
    assert "architecture-bypass-scan" in required
    assert "lock-tests" in required


def test_ci_change_requires_ci_regression_checks() -> None:
    required = required_fast_steps_for_paths(("scripts/ci/step_registry.py",))
    assert "import-smoke" in required
    assert "quality-check" in required
    assert "lock-tests" in required


def test_generated_artifacts_are_blocked() -> None:
    offenders = blocked_artifact_paths(("runtime/data/security/events.jsonl", "storage/schema_version_store.py"))
    assert offenders == ("runtime/data/security/events.jsonl",)


def test_doctor_legacy_wrapper_stays_importable_after_lazy_registry() -> None:
    assert step_doctor.run is step_registry.run_doctor
    assert step_registry.run_doctor.__name__.startswith("lazy_doctor_run_doctor")


def test_impacted_rules_classify_multiple_domains() -> None:
    names = {rule.name for rule in impacted_rules(("billing/recovery_store.py", "security/key_provider.py"))}
    assert names == {"billing", "tenant-security"}


def test_hardened_changed_files_uses_first_parent_when_clean_main_diff_is_empty(monkeypatch) -> None:
    monkeypatch.delenv("BAIOS_CHANGED_FILES", raising=False)
    monkeypatch.delenv("GITHUB_BASE_REF", raising=False)
    monkeypatch.delenv("BAIOS_BASE_REF", raising=False)
    commands: list[tuple[str, ...]] = []

    def fake_run_command(command, **_kwargs) -> CommandOutcome:
        normalized = tuple(command)
        commands.append(normalized)
        if normalized == ("git", "diff", "--name-only", "HEAD^1..HEAD"):
            return CommandOutcome(returncode=0, stdout="runtime/world_state/public_api.py\n", stderr="")
        return CommandOutcome(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(regression_impact_hardened, "run_command", fake_run_command)

    assert regression_impact_hardened.changed_files() == ("runtime/world_state/public_api.py",)
    assert ("git", "diff", "--name-only", "HEAD^1..HEAD") in commands


def test_regression_impact_allows_removing_generated_artifacts(monkeypatch) -> None:
    monkeypatch.setattr(step_regression_impact, "changed_files", lambda: ("runtime/data/security/events.jsonl", ".gitignore"))
    monkeypatch.setattr(step_regression_impact, "deleted_changed_files", lambda: ("runtime/data/security/events.jsonl",))
    monkeypatch.setattr(step_regression_impact, "run_baseline_contract", lambda: (True, "baseline contract matrix passed"))

    ok, message = step_regression_impact.run()

    assert ok is True
    assert "changed_paths=2" in message
