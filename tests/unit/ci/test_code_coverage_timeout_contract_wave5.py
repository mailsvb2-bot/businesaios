from __future__ import annotations

from pathlib import Path


def test_coverage_pytest_run_timeout_is_large_enough_for_expanded_unit_suite() -> None:
    source = Path("scripts/ci/step_code_coverage.py").read_text(encoding="utf-8")

    assert "timeout=360" not in source
    assert "timeout=1200" in source


def test_coverage_xml_reporting_has_bounded_headroom_for_large_repositories() -> None:
    from pathlib import Path
    code = Path("scripts/ci/step_code_coverage.py").read_text(encoding="utf-8")
    assert 'xml_outcome = run_command(_python_command("-m", "coverage", "xml", "-o", str(paths["xml"])), timeout=240)' in code
