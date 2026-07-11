from __future__ import annotations

import json
from dataclasses import asdict
from typing import Any, Callable

from scripts.ci.integrity import auditor
from scripts.ci.integrity.active_test_index import build_active_test_index
from scripts.ci.integrity.second_brain_alias_scan import check_decision_authority_aliases

CANON_INTEGRITY_AUDITOR_RUNNER = True

Check = Callable[[list, dict[str, Any]], list[auditor.Finding]]


def _checks() -> tuple[Check, ...]:
    return (
        auditor.check_single_decision_core,
        check_decision_authority_aliases,
        auditor.check_no_second_brain,
        auditor.check_canonical_flow,
        auditor.check_runtime_side_effects,
        auditor.check_admin_surface,
        auditor.check_registry_contracts,
        lambda files, _spec: auditor.check_import_boundaries(files),
        auditor.check_naming_synonyms,
        lambda files, _spec: auditor.check_evidence_replay_config(files),
    )


def _score_threshold_violations(scorecard: auditor.ScoreCard, spec: dict[str, Any]) -> list[str]:
    thresholds = dict(spec.get("thresholds") or {})
    pairs = (
        ("architectural_integrity", "minimum_architectural_integrity"),
        ("decisioncore_integrity", "minimum_decisioncore_integrity"),
        ("flow_completeness", "minimum_flow_completeness"),
        ("admin_surface_coverage", "minimum_admin_surface_coverage"),
        ("evidence_coverage", "minimum_evidence_coverage"),
        ("runtime_side_effect_safety", "minimum_runtime_side_effect_safety"),
    )
    violations: list[str] = []
    for score_name, threshold_name in pairs:
        score_value = int(getattr(scorecard, score_name))
        threshold_value = int(thresholds.get(threshold_name, 0))
        if score_value < threshold_value:
            violations.append(f"{score_name}_below_{threshold_value}")
    return violations


def run_audit() -> auditor.IntegrityReport:
    spec = auditor.load_spec()
    files = auditor.iter_python_files()
    findings: list[auditor.Finding] = []
    for check in _checks():
        findings.extend(check(files, spec))

    findings.sort(key=lambda item: (item.severity, item.check_id, item.path, item.line, item.message))
    summary = auditor.summarize(findings)
    scorecard = auditor.score(findings, spec)
    fail_on = {str(item) for item in dict(spec.get("thresholds") or {}).get("fail_on_severity", ["P0"])}
    blocking_findings = [item for item in findings if item.severity in fail_on]
    score_violations = _score_threshold_violations(scorecard, spec)

    return auditor.IntegrityReport(
        ok=not blocking_findings and not score_violations,
        scorecard=scorecard,
        findings=findings,
        summary=summary,
    )


def _report_payload(report: auditor.IntegrityReport) -> dict[str, Any]:
    spec = auditor.load_spec()
    active_test_index = build_active_test_index()
    return {
        "artifact": "integrity_auditor",
        "version": spec.get("version"),
        "name": spec.get("name"),
        "goal": spec.get("goal"),
        "ok": report.ok,
        "summary": dict(report.summary),
        "scorecard": asdict(report.scorecard),
        "findings": [asdict(item) for item in report.findings],
        "score_threshold_violations": _score_threshold_violations(report.scorecard, spec),
        "active_test_index": active_test_index.to_json(),
        "claims_production_ready": False,
    }


def _markdown_report(payload: dict[str, Any]) -> str:
    scorecard = dict(payload.get("scorecard") or {})
    summary = dict(payload.get("summary") or {})
    findings = list(payload.get("findings") or [])
    lines = [
        "# BusinessAIOS Integrity Auditor",
        "",
        f"- status: {'passed' if payload.get('ok') else 'blocked'}",
        f"- P0: {summary.get('P0', 0)}",
        f"- P1: {summary.get('P1', 0)}",
        f"- P2: {summary.get('P2', 0)}",
        f"- architectural_integrity: {scorecard.get('architectural_integrity', 0)}",
        f"- decisioncore_integrity: {scorecard.get('decisioncore_integrity', 0)}",
        f"- second_brain_risk: {scorecard.get('second_brain_risk', 'unknown')}",
        "",
        "## Findings",
        "",
    ]
    if not findings:
        lines.append("No findings.")
    else:
        for item in findings:
            lines.append(
                f"- **{item.get('severity')} {item.get('check_id')}** "
                f"`{item.get('path')}:{item.get('line')}` — {item.get('message')}"
            )
    lines.append("")
    return "\n".join(lines)


def write_reports(report: auditor.IntegrityReport) -> None:
    payload = _report_payload(report)
    auditor.REPORT_DIR.mkdir(parents=True, exist_ok=True)
    auditor.JSON_REPORT.write_text(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    auditor.MARKDOWN_REPORT.write_text(_markdown_report(payload), encoding="utf-8")


__all__ = ["CANON_INTEGRITY_AUDITOR_RUNNER", "run_audit", "write_reports"]
