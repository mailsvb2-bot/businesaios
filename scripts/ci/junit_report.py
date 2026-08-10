from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

from scripts.ci.contracts import ExecutionReport
from scripts.ci.fs import safe_write_bytes


def write_junit_xml(path: Path, report: ExecutionReport) -> None:
    testsuite = ET.Element(
        "testsuite", name=f"ci-{report.gate}", tests=str(len(report.steps)),
        failures=str(sum(1 for step in report.steps if step.status == "failed")),
        skipped=str(sum(1 for step in report.steps if step.status == "skipped")),
    )

    for step in report.steps:
        case = ET.SubElement(
            testsuite, "testcase", classname="ci", name=step.name, time=f"{step.duration_ms / 1000:.3f}"
        )
        if step.status in {"failed", "skipped"}:
            detail = ET.SubElement(case, "failure" if step.status == "failed" else "skipped", message=step.message)
            detail.text = step.message

    safe_write_bytes(path, ET.tostring(testsuite, encoding="utf-8", xml_declaration=True))
