from __future__ import annotations

from pathlib import Path


def test_coverage_pytest_run_timeout_is_large_enough_for_expanded_unit_suite() -> None:
    source = Path("scripts/ci/step_code_coverage.py").read_text(encoding="utf-8")

    assert "timeout=360" not in source
    assert "timeout=1200" in source
