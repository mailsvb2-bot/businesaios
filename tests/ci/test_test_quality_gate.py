from __future__ import annotations

from scripts.ci.step_test_quality import build_report


def test_test_quality_report_has_inventory() -> None:
    report = build_report()

    assert report.total_test_files > 0
    assert report.total_test_functions > 0
    assert isinstance(report.findings, list)
