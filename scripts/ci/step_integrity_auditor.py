from __future__ import annotations

from scripts.ci.integrity.auditor import run_audit, write_reports


def run() -> tuple[bool, str]:
    report = run_audit()
    write_reports(report)
    if report.ok:
        return True, f"integrity auditor passed; summary={report.summary}"
    return False, f"integrity auditor failed; summary={report.summary}; see reports/integrity/integrity.json"
