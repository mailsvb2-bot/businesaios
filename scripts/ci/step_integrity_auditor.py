from __future__ import annotations

from scripts.ci.integrity.auditor import run_audit, write_reports


def _blocking_excerpt(report) -> str:
    blockers = [item for item in report.findings if item.severity == "P0"]
    if not blockers:
        return "blocking=none"
    parts = [f"{item.check_id}@{item.path}:{item.line}:{item.message}" for item in blockers[:8]]
    if len(blockers) > len(parts):
        parts.append(f"{len(blockers) - len(parts)} more")
    return "blocking=" + " | ".join(parts)


def run() -> tuple[bool, str]:
    report = run_audit()
    write_reports(report)
    excerpt = _blocking_excerpt(report)
    if report.ok:
        return True, f"integrity auditor passed; summary={report.summary}; {excerpt}"
    return False, f"integrity auditor failed; summary={report.summary}; {excerpt}; see reports/integrity/integrity.json"
