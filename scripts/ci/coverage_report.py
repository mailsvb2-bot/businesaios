from __future__ import annotations

import io
import xml.etree.ElementTree as ET
from pathlib import Path

from scripts.ci.contracts import ExecutionReport
from scripts.ci.fs import safe_write_bytes


def write_ci_execution_summary_xml(path: Path, report: ExecutionReport) -> None:
    """Write a CI execution summary XML, not code coverage.

    This artifact intentionally reports gate/step status only. It must never be
    interpreted as coverage.py metrics or production readiness evidence.
    """

    root = ET.Element(
        "ci-execution-summary",
        version="ci-canon-v8",
        gate=report.gate,
        success=str(report.success).lower(),
        claims_code_coverage="false",
        claims_production_ready="false",
    )
    summary = ET.SubElement(root, "summary")
    summary.set("steps", str(len(report.steps)))
    summary.set("failed_steps", str(sum(1 for step in report.steps if step.status == "failed")))
    summary.set("skipped_steps", str(sum(1 for step in report.steps if step.status == "skipped")))
    summary.set("coverage_kind", "not_code_coverage")

    buffer = io.BytesIO()
    ET.ElementTree(root).write(buffer, encoding="utf-8", xml_declaration=True)
    safe_write_bytes(path, buffer.getvalue())


# Backward-compatible name for existing callers. The emitted XML is intentionally
# not a coverage report and carries explicit non-coverage claims.
def write_coverage_stub_xml(path: Path, report: ExecutionReport) -> None:
    write_ci_execution_summary_xml(path, report)


__all__ = ["write_ci_execution_summary_xml", "write_coverage_stub_xml"]
