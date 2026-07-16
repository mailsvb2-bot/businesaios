from __future__ import annotations

from scripts.ci.integrity.auditor import (
    IntegrityReport,
    iter_python_files,
    load_spec,
    run_audit,
    score,
    summarize,
    write_reports,
)
from scripts.ci.integrity.decision_authority_alias_scan import check_decision_authority_aliases


def _run_canonical_integrity_report() -> IntegrityReport:
    report = run_audit()
    spec = load_spec()
    alias_findings = check_decision_authority_aliases(iter_python_files(), spec)
    if not alias_findings:
        return report

    findings = [*report.findings, *alias_findings]
    fail_on = set(spec["thresholds"]["fail_on_severity"])
    return IntegrityReport(
        ok=not any(item.severity in fail_on for item in findings),
        scorecard=score(findings, spec),
        findings=findings,
        summary=summarize(findings),
    )


def _blocking_excerpt(report: IntegrityReport) -> str:
    blockers = [item for item in report.findings if item.severity == "P0"]
    if not blockers:
        return "blocking=none"
    parts = [f"{item.check_id}@{item.path}:{item.line}:{item.message}" for item in blockers[:8]]
    if len(blockers) > len(parts):
        parts.append(f"{len(blockers) - len(parts)} more")
    return "blocking=" + " | ".join(parts)


def run() -> tuple[bool, str]:
    report = _run_canonical_integrity_report()
    write_reports(report)
    excerpt = _blocking_excerpt(report)
    if report.ok:
        return True, f"integrity auditor passed; summary={report.summary}; {excerpt}"
    return False, f"integrity auditor failed; summary={report.summary}; {excerpt}; see reports/integrity/integrity.json"
