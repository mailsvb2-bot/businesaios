from __future__ import annotations

from pathlib import Path


def test_coverage_report_timeouts_and_required_xml_gate() -> None:
    source = Path("scripts/ci/step_code_coverage.py").read_text(encoding="utf-8")

    assert '"xml", "-o", str(paths["xml"])), timeout=240)' in source and 'violations.append("coverage_xml_failed")' in source
    assert "timeout=1200" in source
