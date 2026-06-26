from __future__ import annotations

from scripts.ci.plan_registry import plan_for_gate


def _names(gate: str) -> list[str]:
    return [step.name for step in plan_for_gate(gate).steps]


def _assert_before(names: list[str], left: str, right: str) -> None:
    assert names.index(left) < names.index(right)


def test_gate_order_keeps_core_preflight_before_heavy_checks() -> None:
    for gate in ("fast", "full", "release", "pre-release"):
        names = _names(gate)
        assert names[:3] == ["assert-project-shape", "dependency-lock", "doctor-check"]
        _assert_before(names, "doctor-check", "import-smoke")
        _assert_before(names, "import-smoke", "boot-smoke")
        _assert_before(names, "quality-check", "lock-tests")


def test_release_gate_keeps_release_proof_after_regression_locks() -> None:
    names = _names("release")
    _assert_before(names, "lock-tests", "postgres-contract")
    _assert_before(names, "postgres-contract", "verify-release")
    _assert_before(names, "verify-release", "build-artifact")


def test_doctor_gate_stays_minimal() -> None:
    assert _names("doctor") == ["assert-project-shape", "doctor-check"]
