from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

from scripts.ci.contracts import ExecutionReport


def write_execution_xml(path: Path, report: ExecutionReport) -> None:
    root = ET.Element(
        "execution",
        version="ci-canon-v7",
        gate=report.gate,
        success=str(report.success).lower(),
    )
    summary = ET.SubElement(root, "summary")
    summary.set("steps", str(len(report.steps)))
    summary.set("failed_steps", str(sum(1 for step in report.steps if step.status == "failed")))
    summary.set("skipped_steps", str(sum(1 for step in report.steps if step.status == "skipped")))

    for step in report.steps:
        step_node = ET.SubElement(root, "step")
        step_node.set("name", step.name)
        step_node.set("status", step.status)
        step_node.set("duration_ms", str(step.duration_ms))
        step_node.text = step.message

    tree = ET.ElementTree(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    tree.write(path, encoding="utf-8", xml_declaration=True)
