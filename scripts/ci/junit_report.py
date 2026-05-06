from __future__ import annotations

import io
import xml.etree.ElementTree as ET
from pathlib import Path

from scripts.ci.contracts import ExecutionReport
from scripts.ci.fs import safe_write_bytes


def write_junit_xml(path: Path, report: ExecutionReport) -> None:
    testsuite = ET.Element(
        "testsuite",
        name=f"ci-{report.gate}",
        tests=str(len(report.steps)),
        failures=str(sum(1 for step in report.steps if step.status == "failed")),
        skipped=str(sum(1 for step in report.steps if step.status == "skipped")),
    )

    for step in report.steps:
        case = ET.SubElement(
            testsuite,
            "testcase",
            classname="ci",
            name=step.name,
            time=f"{step.duration_ms / 1000:.3f}",
        )
        if step.status == "failed":
            failure = ET.SubElement(case, "failure", message=step.message)
            failure.text = step.message
        elif step.status == "skipped":
            skipped = ET.SubElement(case, "skipped", message=step.message)
            skipped.text = step.message

    buffer = io.BytesIO()
    ET.ElementTree(testsuite).write(buffer, encoding="utf-8", xml_declaration=True)
    safe_write_bytes(path, buffer.getvalue())
