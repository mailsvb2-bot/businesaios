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
        "production-boot",
    ]
    assert callable(handler_for_step("postgres-contract"))
    assert callable(handler_for_step("production-boot"))


def test_release_plans_include_postgres_contract_and_production_boot_before_release_artifacts() -> None:
    release_steps = [step.name for step in plan_for_gate("release").steps]
    prerelease_steps = [step.name for step in plan_for_gate("pre-release").steps]

    assert "postgres-contract" in release_steps
    assert "production-boot" in release_steps
    assert "postgres-contract" in prerelease_steps
    assert "production-boot" in prerelease_steps
    assert release_steps.index("postgres-contract") < release_steps.index("production-boot") < release_steps.index("verify-release")
    assert prerelease_steps.index("postgres-contract") < prerelease_steps.index("production-boot") < prerelease_steps.index("verify-release")


def test_cli_accepts_production_boot_gate() -> None:
    parser = build_parser()
    args = parser.parse_args(["--gate", "production-boot"])

    assert args.gate == "production-boot"
