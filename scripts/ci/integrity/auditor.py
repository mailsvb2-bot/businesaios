from __future__ import annotations

import ast
import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from scripts.ci.integrity.active_test_index import build_active_test_index

ROOT = Path(__file__).resolve().parents[3]
SPEC_PATH = ROOT / "scripts" / "ci" / "specs" / "integrity_auditor_rules.json"
REPORT_DIR = ROOT / "reports" / "integrity"
JSON_REPORT = REPORT_DIR / "integrity.json"
MARKDOWN_REPORT = REPORT_DIR / "integrity.md"
CANONICAL_DECISION_CORE_PATH = "core/ai/decision_core.py"
PATH_ONLY_ENGINE_TERMS = frozenset({"strategy_engine", "decision_engine", "planner_engine"})

SKIP_DIRS = {
    ".git",
    ".venv",
    "__pycache__",
    ".pytest_cache",
    ".ruff_cache",
    ".mypy_cache",
    "node_modules",
    "target",
    "reports",
}


@dataclass(frozen=True)
class Finding:
    check_id: str
    severity: str
    title: str
    path: str
    line: int
    message: str
    recommendation: str


@dataclass(frozen=True)
class ScoreCard:
    architectural_integrity: int
    decisioncore_integrity: int
    second_brain_risk: str
    flow_completeness: int
    admin_surface_coverage: int
    evidence_coverage: int
    runtime_side_effect_safety: int


@dataclass(frozen=True)
class IntegrityReport:
    ok: bool
    scorecard: ScoreCard
    findings: list[Finding]
    summary: dict[str, int]


def load_spec() -> dict[str, Any]:
    return json.loads(SPEC_PATH.read_text(encoding="utf-8"))


def iter_python_files() -> list[Path]:
    files: list[Path] = []
    for path in ROOT.rglob("*.py"):
        rel_parts = set(path.relative_to(ROOT).parts)
        if rel_parts & SKIP_DIRS:
            continue
        files.append(path)
    return sorted(files)


def rel(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def parse_file(path: Path) -> ast.AST | None:
    try:
        return ast.parse(path.read_text(encoding="utf-8"), filename=rel(path))
    except SyntaxError:
        return None


def dotted_name(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        base = dotted_name(node.value)
        return f"{base}.{node.attr}" if base else node.attr
    if isinstance(node, ast.Call):
        return dotted_name(node.func)
    return ""


def collect_text_index(files: list[Path]) -> dict[str, str]:
    index: dict[str, str] = {}
    for path in files:
        try:
            index[rel(path)] = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
    return index


def finding(check_id: str, severity: str, title: str, path: Path | str, line: int, message: str, recommendation: str) -> Finding:
    return Finding(
        check_id=check_id,
        severity=severity,
        title=title,
        path=path if isinstance(path, str) else rel(path),
        line=line,
        message=message,
        recommendation=recommendation,
    )


def _executable_decision_authority_names(spec: dict[str, Any]) -> set[str]:
    configured = spec.get("executable_decision_authority_names")
    if isinstance(configured, list) and all(isinstance(item, str) for item in configured):
        return set(configured)
    return {"DecisionCore", "DecisionCoreEngine", "DecisionEngine", "PlannerEngine"}


def check_single_decision_core(files: list[Path], spec: dict[str, Any]) -> list[Finding]:
    executable_names = _executable_decision_authority_names(spec)
    findings: list[Finding] = []
    executable_defs: list[tuple[Path, int, str, str]] = []

    for path in files:
        if rel(path).startswith("tests/"):
            continue
        tree = parse_file(path)
        if tree is None:
            continue
        for node in ast.walk(tree):
            if not isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if node.name not in executable_names:
                continue
            executable_defs.append((path, getattr(node, "lineno", 1), node.name, type(node).__name__))

    core_defs = [item for item in executable_defs if rel(item[0]) == CANONICAL_DECISION_CORE_PATH and item[2] == "DecisionCore"]
    if not core_defs:
        findings.append(
            finding(
                "P0_SINGLE_DECISION_CORE",
                "P0",
                "DecisionCore not detected",
                "repo",
                1,
                "No canonical DecisionCore definition was found by the auditor.",
                "Declare the single canonical DecisionCore in core/ai/decision_core.py and keep all other decision authority as callers.",
            )
        )

    for path, line, name, node_kind in executable_defs:
        if rel(path) == CANONICAL_DECISION_CORE_PATH and name == "DecisionCore" and node_kind == "ClassDef":
            continue
        findings.append(
            finding(
                "P0_SINGLE_DECISION_CORE",
                "P0",
                "Potential competing executable decision authority",
                path,
                line,
                f"Found executable `{name}` ({node_kind}) outside the canonical DecisionCore.",
                "Remove this authority or route it through the single canonical DecisionCore as a non-authoritative caller.",
            )
        )

    return findings


def check_no_second_brain(files: list[Path], spec: dict[str, Any]) -> list[Finding]:
    terms = spec["second_brain_suspicious_terms"]
    out: list[Finding] = []
    for path in files:
        r = rel(path)
        lowered_path = r.lower()
        if "/tests/" in f"/{r}":
            continue
        for term in terms:
            if term not in lowered_path:
                continue
            severity = "P1" if term in PATH_ONLY_ENGINE_TERMS else "P0"
            check_id = "P1_ENGINE_NAMING_SURFACE" if severity == "P1" else "P0_NO_SECOND_BRAIN"
            out.append(finding(
                check_id,
                severity,
                "Potential second-brain surface",
                path,
                1,
                f"Suspicious second-brain term `{term}` appears in path.",
                "Keep planning/decision/memory authority behind the canonical DecisionCore and registry contracts.",
            ))
    return out


def check_canonical_flow(files: list[Path], spec: dict[str, Any]) -> list[Finding]:
    text = "\n".join(collect_text_index(files).values()).lower()
    required = spec["canonical_flow"]
    missing = [term for term in required if term not in text]
    if not missing:
        return []
    return [finding(
        "P1_CANONICAL_FLOW",
        "P1",
        "Canonical flow terms missing",
        "repo",
        1,
        "Missing canonical flow concepts: " + ", ".join(missing),
        "Ensure the signal→state→decision→policy/guard→execution→verification→evidence→archive path is explicitly represented and tested.",
    )]


def check_runtime_side_effects(files: list[Path], spec: dict[str, Any]) -> list[Finding]:
    calls = set(spec["side_effect_calls"])
    approved_roots = tuple(spec["approved_side_effect_roots"])
    out: list[Finding] = []

    for path in files:
        r = rel(path)
        if r.startswith(approved_roots) or r.startswith("tests/"):
            continue
        tree = parse_file(path)
        if tree is None:
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                name = dotted_name(node.func)
                if name in calls:
                    out.append(finding(
                        "P1_RUNTIME_SIDE_EFFECTS",
                        "P1",
                        "Side effect outside approved execution roots",
                        path,
                        getattr(node, "lineno", 1),
                        f"Call `{name}` appears outside approved runtime/infrastructure/connectors/scripts roots.",
                        "Move the side effect behind a sealed executor/effect gateway with guard, idempotency, verification and evidence.",
                    ))
    return out


def check_admin_surface(files: list[Path], spec: dict[str, Any]) -> list[Finding]:
    index = collect_text_index(files)
    all_text = "\n".join(index.values()).lower()
    required = spec["admin_required_terms"]
    missing = [term for term in required if term not in all_text]
    if not missing:
        return []
    return [finding(
        "P1_ADMIN_SURFACE",
        "P1",
        "Admin/control-plane visibility incomplete",
        "repo",
        1,
        "Missing admin/control-plane observability terms: " + ", ".join(missing),
        "Expose capability status, risk, evidence and health through admin/control-plane surfaces.",
    )]


def check_registry_contracts(files: list[Path], spec: dict[str, Any]) -> list[Finding]:
    all_text = "\n".join(collect_text_index(files).values()).lower()
    missing = [term for term in spec["registry_required_terms"] if term not in all_text]
    if not missing:
        return []
    return [finding(
        "P1_REGISTRY_COMPLETENESS",
        "P1",
        "Registry/manifest vocabulary incomplete",
        "repo",
        1,
        "Missing registry contract terms: " + ", ".join(missing),
        "Keep capability/action/policy/guard registries explicit and cross-check them against manifests/tests/admin.",
    )]


def check_import_boundaries(files: list[Path]) -> list[Finding]:
    out: list[Finding] = []
    forbidden = {
        "core": ("telegram", "aiogram", "fastapi", "flask", "django"),
        "interfaces": ("runtime.registry", "runtime.boot"),
    }

    for path in files:
        r = rel(path)
        tree = parse_file(path)
        if tree is None:
            continue
        root = r.split("/", 1)[0]
        forbidden_terms = forbidden.get(root)
        if not forbidden_terms:
            continue
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                names: list[str] = []
                if isinstance(node, ast.Import):
                    names = [alias.name for alias in node.names]
                else:
                    names = [node.module or ""]
                for imported in names:
                    if imported.startswith(forbidden_terms):
                        out.append(finding(
                            "P1_IMPORT_BOUNDARY",
                            "P1",
                            "Layer import boundary violation",
                            path,
                            getattr(node, "lineno", 1),
                            f"`{r}` imports `{imported}`, which can invert canonical layer direction.",
                            "Move framework/runtime-specific dependency to adapter/infrastructure layer.",
                        ))
    return out


def check_naming_synonyms(files: list[Path], spec: dict[str, Any]) -> list[Finding]:
    all_text = "\n".join(collect_text_index(files).values()).lower()
    out: list[Finding] = []
    for group in spec["canonical_name_groups"]:
        present = [term for term in group if re.search(rf"\b{re.escape(term)}\b", all_text)]
        if len(present) >= 3:
            out.append(finding(
                "P1_NAMING_SYNONYMS",
                "P1",
                "Potential canonical naming drift",
                "repo",
                1,
                "Multiple synonym names are widely present: " + ", ".join(present),
                "Define canonical terminology and explicit aliases in architecture docs/spec.",
            ))
    return out


def check_evidence_replay_config(files: list[Path]) -> list[Finding]:
    all_text = "\n".join(collect_text_index(files).values()).lower()
    checks = [
        ("P2_EVIDENCE_COVERAGE", "evidence", "Evidence vocabulary not visible enough", "Ensure decisions/effects/verifications write evidence records."),
        ("P2_REPLAY_DETERMINISM", "replay", "Replay determinism vocabulary not visible enough", "Add replay snapshot/reconstruction tests for decision determinism."),
        ("P2_CONFIG_SPLIT_BRAIN", "config", "Config vocabulary not visible enough", "Keep config sources centralized and audited for split-brain risk."),
        ("P2_HUMAN_OVERRIDE", "override", "Human override vocabulary not visible enough", "Expose pause/approval/rollback/blast-radius controls for autonomy."),
    ]
    out: list[Finding] = []
    for check_id, term, title, recommendation in checks:
        if term not in all_text:
            out.append(finding(check_id, "P2", title, "repo", 1, f"`{term}` not found in repository text index.", recommendation))
    return out


def summarize(findings: list[Finding]) -> dict[str, int]:
    summary = {"P0": 0, "P1": 0, "P2": 0}
    for f in findings:
        summary[f.severity] = summary.get(f.severity, 0) + 1
    return summary


def score(findings: list[Finding], spec: dict[str, Any]) -> ScoreCard:
    summary = summarize(findings)
    p0 = summary.get("P0", 0)
    p1 = summary.get("P1", 0)
    p2 = summary.get("P2", 0)

    return ScoreCard(
        architectural_integrity=max(0, 100 - p0 * 15 - p1 * 5 - p2 * 2),
        decisioncore_integrity=max(0, 100 - len([f for f in findings if "DECISION" in f.check_id]) * 20),
        second_brain_risk="high" if any(f.check_id == "P0_NO_SECOND_BRAIN" for f in findings) else ("medium" if p0 else "low"),
        flow_completeness=max(0, 100 - len([f for f in findings if "FLOW" in f.check_id]) * 40),
        admin_surface_coverage=max(0, 100 - len([f for f in findings if "ADMIN" in f.check_id]) * 35),
        evidence_coverage=max(0, 100 - len([f for f in findings if "EVIDENCE" in f.check_id]) * 30),
        runtime_side_effect_safety=max(0, 100 - len([f for f in findings if "SIDE_EFFECT" in f.check_id]) * 20),
    )


def run_audit() -> IntegrityReport:
    spec = load_spec()
    files = iter_python_files()
    findings: list[Finding] = []
    findings.extend(check_single_decision_core(files, spec))
    findings.extend(check_no_second_brain(files, spec))
    findings.extend(check_canonical_flow(files, spec))
    findings.extend(check_runtime_side_effects(files, spec))
    findings.extend(check_admin_surface(files, spec))
    findings.extend(check_registry_contracts(files, spec))
    findings.extend(check_import_boundaries(files))
    findings.extend(check_naming_synonyms(files, spec))
    findings.extend(check_evidence_replay_config(files))

    card = score(findings, spec)
    summary = summarize(findings)
    fail_on = set(spec["thresholds"]["fail_on_severity"])
    ok = not any(f.severity in fail_on for f in findings)
    return IntegrityReport(ok=ok, scorecard=card, findings=findings, summary=summary)


def write_reports(report: IntegrityReport) -> None:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    JSON_REPORT.write_text(
        json.dumps({
            "ok": report.ok,
            "scorecard": asdict(report.scorecard),
            "summary": report.summary,
            "active_test_index": build_active_test_index().to_json(),
            "findings": [asdict(f) for f in report.findings],
        }, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    lines = [
        "# BusinessAIOS Integrity Auditor",
        "",
        f"ok: `{report.ok}`",
        "",
        "## Scorecard",
        "",
    ]
    for key, value in asdict(report.scorecard).items():
        lines.append(f"- **{key}**: `{value}`")
    active_index = build_active_test_index()
    lines.extend(["", "## Active Test Index", ""])
    lines.append(f"- **total_test_files**: `{active_index.inventory.total_test_files}`")
    lines.append(f"- **all_tests_gate_present**: `{active_index.inventory.all_tests_gate_present}`")
    lines.append(f"- **pytest_root**: `{active_index.inventory.pytest_root}`")
    lines.append("")
    for item in active_index.risks:
        lines.append(
            f"- **{item.risk_id}**: `{item.status}`; "
            f"tests=`{len(item.test_files_found)}`; "
            f"gates=`{', '.join(item.active_gates) or 'none'}`; "
            f"steps=`{', '.join(item.active_steps) or 'none'}`"
        )

    lines.extend(["", "## Findings", ""])
    if not report.findings:
        lines.append("No findings.")
    else:
        for f in report.findings:
            lines.append(f"- **{f.severity} {f.check_id}** `{f.path}:{f.line}` — {f.title}. {f.message} Recommendation: {f.recommendation}")
    MARKDOWN_REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    report = run_audit()
    write_reports(report)
    print(f"integrity auditor ok={report.ok} summary={report.summary}")
    print(f"integrity report: {JSON_REPORT.relative_to(ROOT)}")
    return 0 if report.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
