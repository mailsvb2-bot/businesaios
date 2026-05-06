from __future__ import annotations

from scripts.ci.plan_registry import plan_for_gate


def _names(gate: str) -> tuple[str, ...]:
    return tuple(step.name for step in plan_for_gate(gate).steps)


def test_doctor_gate_is_lightweight_and_bounded() -> None:
    assert _names("doctor") == ("assert-project-shape", "doctor-check")


def test_fast_gate_proves_import_smoke_before_lock_tests() -> None:
    names = _names("fast")
    assert "import-smoke" in names
    assert names.index("import-smoke") < names.index("lock-tests")
    assert "canon-audit" not in names


def test_full_gate_keeps_heavy_canon_after_import_smoke() -> None:
    names = _names("full")
    assert "canon-audit" in names
    assert names.index("import-smoke") < names.index("canon-audit")
