from __future__ import annotations

import os

from scripts.ci.execution import _step_environment
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


def test_release_gate_deduplicates_python_suites_via_coverage_superset() -> None:
    full_names, release_names = set(_names("full")), set(_names("release"))
    assert {"unit-tests", "integration-tests"} <= full_names
    assert {"unit-tests", "integration-tests"}.isdisjoint(release_names)
    assert "code-coverage" in release_names


def test_release_step_environment_hides_dsn_until_runtime_proof(monkeypatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql://proof")
    monkeypatch.setenv("POSTGRES_DSN", "postgresql://proof")
    with _step_environment(gate="release", step_name="quality-check"):
        assert "DATABASE_URL" not in os.environ
        assert "POSTGRES_DSN" not in os.environ
    assert os.environ["DATABASE_URL"] == "postgresql://proof"
    with _step_environment(gate="release", step_name="postgres-live"):
        assert os.environ["DATABASE_URL"] == "postgresql://proof"
        assert os.environ["PGCONNECT_TIMEOUT"] == "10"
        assert "lock_timeout=10000" in os.environ["PGOPTIONS"]
