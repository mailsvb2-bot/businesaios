from __future__ import annotations

import io
import xml.etree.ElementTree as ET
from pathlib import Path

from scripts.ci.contracts import ExecutionReport
from scripts.ci.fs import safe_write_bytes


def write_coverage_stub_xml(path: Path, report: ExecutionReport) -> None:
    root = ET.Element(
        "coverage",
        version="ci-canon-v7",
        gate=report.gate,
        success=str(report.success).lower(),
    )
    summary = ET.SubElement(root, "summary")
    summary.set("steps", str(len(report.steps)))
    summary.set("failed_steps", str(sum(1 for step in report.steps if step.status == "failed")))
    summary.set("skipped_steps", str(sum(1 for step in report.steps if step.status == "skipped")))

    buffer = io.BytesIO()
    ET.ElementTree(root).write(buffer, encoding="utf-8", xml_declaration=True)
    safe_write_bytes(path, buffer.getvalue())
