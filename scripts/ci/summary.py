from __future__ import annotations

from pathlib import Path

from scripts.ci.contracts import ExecutionReport
from scripts.ci.fs import safe_write_text
from scripts.ci.paths import summaries_dir


def write_failure_summary(report: ExecutionReport) -> Path:
    path = summaries_dir() / f"{report.gate}.failure-summary.txt"

    failed = [step for step in report.steps if step.status == "failed"]
    skipped = [step for step in report.steps if step.status == "skipped"]

    lines: list[str] = [
        f"gate={report.gate}",
        f"success={report.success}",
        f"goal={report.goal}",
        "",
    ]

    if failed:
        lines.append("failed_steps:")
        for step in failed:
            lines.append(
                f"- name={step.name} duration_ms={step.duration_ms} message={step.message}"
            )
        lines.append("")

    if skipped:
        lines.append("skipped_steps:")
        for step in skipped:
            lines.append(
                f"- name={step.name} duration_ms={step.duration_ms} message={step.message}"
            )
        lines.append("")

    if not failed and not skipped:
        lines.append("no failures or skips recorded")

    safe_write_text(path, "\n".join(lines).rstrip() + "\n", encoding="utf-8")
    return path
