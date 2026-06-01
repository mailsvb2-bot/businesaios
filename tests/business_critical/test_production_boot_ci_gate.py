from __future__ import annotations

from scripts.ci.cli import build_parser
from scripts.ci.plan_registry import plan_for_gate
from scripts.ci.step_registry import handler_for_step


def test_production_boot_gate_is_registered() -> None:
    plan = plan_for_gate("production-boot")

    assert plan.gate == "production-boot"
    assert [step.name for step in plan.steps] == [
        "assert-project-shape",
        "doctor-check",
        "postgres-contract",
        "postgres-migrations",
        "postgres-live",
        "container-runtime",
        "production-boot",
    ]
    assert callable(handler_for_step("postgres-contract"))
    assert callable(handler_for_step("postgres-migrations"))
    assert callable(handler_for_step("postgres-live"))
    assert callable(handler_for_step("container-runtime"))
    assert callable(handler_for_step("production-boot"))


def test_release_plans_include_container_runtime_before_production_boot_and_release_artifacts() -> None:
    release_steps = [step.name for step in plan_for_gate("release").steps]
    prerelease_steps = [step.name for step in plan_for_gate("pre-release").steps]

    for step in ("postgres-contract", "postgres-migrations", "postgres-live", "container-runtime", "production-boot"):
        assert step in release_steps
        assert step in prerelease_steps
    assert release_steps.index("postgres-contract") < release_steps.index("postgres-migrations") < release_steps.index("postgres-live") < release_steps.index("container-runtime") < release_steps.index("production-boot") < release_steps.index("verify-release")
    assert prerelease_steps.index("postgres-contract") < prerelease_steps.index("postgres-migrations") < prerelease_steps.index("postgres-live") < prerelease_steps.index("container-runtime") < prerelease_steps.index("production-boot") < prerelease_steps.index("verify-release")


def test_cli_accepts_production_boot_gate() -> None:
    parser = build_parser()
    args = parser.parse_args(["--gate", "production-boot"])

    assert args.gate == "production-boot"
