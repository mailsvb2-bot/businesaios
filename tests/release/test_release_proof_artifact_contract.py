from __future__ import annotations

from scripts.ci.plan_registry import plan_for_gate


def _step_names(gate: str) -> tuple[str, ...]:
    return tuple(step.name for step in plan_for_gate(gate).steps)


def test_release_gate_contains_full_runtime_proof_chain() -> None:
    names = _step_names("release")
    required = (
        "postgres-contract",
        "postgres-migrations",
        "postgres-live",
        "container-runtime",
        "staging-runtime",
        "production-boot",
        "verify-release",
        "build-artifact",
    )
    for step in required:
        assert step in names

    assert names.index("postgres-contract") < names.index("postgres-migrations")
    assert names.index("postgres-migrations") < names.index("postgres-live")
    assert names.index("postgres-live") < names.index("container-runtime")
    assert names.index("container-runtime") < names.index("staging-runtime")
    assert names.index("staging-runtime") < names.index("production-boot")
    assert names.index("production-boot") < names.index("verify-release")
    assert names.index("verify-release") < names.index("build-artifact")


def test_pre_release_gate_contains_runtime_proof_before_verify_release() -> None:
    names = _step_names("pre-release")
    required = (
        "postgres-contract",
        "postgres-migrations",
        "postgres-live",
        "container-runtime",
        "staging-runtime",
        "production-boot",
        "verify-release",
    )
    for step in required:
        assert step in names

    assert names.index("production-boot") < names.index("verify-release")
