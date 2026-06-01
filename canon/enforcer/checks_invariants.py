from __future__ import annotations

from pathlib import Path

from canon.enforcer.rules import (
    FORBIDDEN_SECOND_BRAIN_FILE_HINTS,
    REPO_ROOT,
    SYNONYM_NAMESPACE_PAIRS,
    iter_py_files,
    nontrivial_py_count,
    path_str,
)


def check_required_invariants(report, root: Path = REPO_ROOT) -> None:
    required = ["core/ai/decision_core.py", "runtime/executor.py", "runtime/guard.py", "runtime/platform", "interfaces"]
    for rel in required:
        if not (root / rel).exists():
            report.add(severity="critical", kind="missing-invariant", path=rel, line=None, message=f"Required canonical path missing: {rel}", hint="Restore canonical architecture before further changes.")


def check_second_brain_file_hints(report, root: Path = REPO_ROOT) -> None:
    for path in iter_py_files(root):
        if path.name in FORBIDDEN_SECOND_BRAIN_FILE_HINTS:
            report.add(severity="high", kind="second-brain-file", path=path_str(path), line=None, message=f"Suspicious second-brain file detected: {path.name}", hint="Merge this role into DecisionCore or convert it into proposal-only logic.")


def _namespace_role(path: Path) -> str:
    marker = path / "CANON_NAMESPACE_ROLE.md"
    if not marker.exists():
        return ""
    try:
        return marker.read_text(encoding="utf-8", errors="replace").strip()
    except OSError:
        return ""


def check_synonym_namespaces(report, root: Path = REPO_ROOT) -> None:
    for a, b in SYNONYM_NAMESPACE_PAIRS:
        pa = root / a
        pb = root / b
        if not (pa.exists() and pb.exists()):
            continue
        role_a = _namespace_role(pa)
        role_b = _namespace_role(pb)
        if role_a and role_b and role_a != role_b:
            continue
        count_a = nontrivial_py_count(pa)
        count_b = nontrivial_py_count(pb)
        if count_a == 0 or count_b == 0:
            continue
        severity = "high" if a == "core/policy" and b == "core/policies" else "medium"
        report.add(severity=severity, kind="synonym-namespace", path=f"{a} <-> {b}", line=None, message=f"Competing namespace roots detected (left={count_a}, right={count_b}).", hint="Keep one canonical namespace and migrate imports or document explicit ownership.")
