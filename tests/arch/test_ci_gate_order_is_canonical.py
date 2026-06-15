from __future__ import annotations

from scripts.ci.plan_registry import plan_for_gate


def _names(gate: str) -> list[str]:
    return [step.name for step in plan_for_gate(gate).steps]


def test_gate_order_is_canonical() -> None:
    assert _names("doctor") == [
        "assert-project-shape",
        "dependency-lock",
        "doctor-check",
    ]
    assert _names("fast") == [
        "assert-project-shape",
        "dependency-lock",
        "doctor-check",
        "import-smoke",
        "boot-smoke",
        "quality-check",
        "architecture-bypass-scan",
        "async-test-contract",
        "lock-tests",
    ]
    assert _names("full") == [
        "assert-project-shape",
        "dependency-lock",
        "doctor-check",
        "import-smoke",
        "boot-smoke",
        "demo-e2e-smoke",
        "quality-check",
        "canon-audit",
        "architecture-bypass-scan",
        "async-test-contract",
        "lock-tests",
        "unit-tests",
        "integration-tests",
        "business-critical-tests",
        "rust-safety-core",
    ]
    assert _names("release") == [
        "assert-project-shape",
        "dependency-lock",
        "doctor-check",
        "import-smoke",
        "boot-smoke",
        "demo-e2e-smoke",
        "quality-check",
        "canon-audit",
        "architecture-bypass-scan",
        "async-test-contract",
        "lock-tests",
        "unit-tests",
        "integration-tests",
        "business-critical-tests",
        "code-coverage",
        "rust-safety-core",
        "rust-supply-chain",
        "postgres-contract",
        "postgres-migrations",
        "postgres-live",
        "container-runtime",
        "staging-runtime",
        "production-boot",
        "verify-release",
        "build-artifact",
    ]
