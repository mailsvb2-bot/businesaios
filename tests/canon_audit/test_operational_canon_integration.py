from __future__ import annotations

from pathlib import Path

from tools.canon_audit.checks import OPERATIONAL_CANON_INCLUDE_PATHS, run_operational_canon_checks


REPO_ROOT = Path(__file__).resolve().parents[2]


def test_operational_scope_is_scoped_to_canon_surface() -> None:
    assert OPERATIONAL_CANON_INCLUDE_PATHS == (
        "canon",
        "tools/canon_audit",
        "scripts/ci",
        "tests/canon_audit",
    )


def test_operational_canon_passes_on_repo() -> None:
    report = run_operational_canon_checks(REPO_ROOT)
    assert report.passed is True
    assert report.admission_score_100 == 100.0
    assert report.violations == ()
