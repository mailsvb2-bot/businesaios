from __future__ import annotations

import ast
import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List
from collections.abc import Sequence

from tools.canon_audit.contracts import ArchitectureViolation
from tools.canon_audit.import_graph import collect_python_files, module_name_from_path

ALLOWED_PREFIXES = (
    "application.policy",
    "application.decision",
    "application.world_state",
    "application.capability",
    "application.governance",
)


@dataclass(frozen=True)
class NumericSnippet:
    module_name: str
    fingerprint: str
    rendered: str


def _is_allowed(module_name: str) -> bool:
    return any(module_name == p or module_name.startswith(p + ".") for p in ALLOWED_PREFIXES)


def _looks_like_policy_name(name: str) -> bool:
    lowered = name.lower()
    return any(m in lowered for m in ("score", "penalty", "threshold", "confidence", "risk", "weight", "bonus", "budget", "limit", "window"))


def _fp(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def scan_policy_duplication_and_leakage(root: Path, include_paths: Sequence[str] | None = None) -> list[ArchitectureViolation]:
    violations: list[ArchitectureViolation] = []
    snippets: list[NumericSnippet] = []

    for file_path in collect_python_files(root, include_paths=include_paths):
        module_name = module_name_from_path(root, file_path)
        tree = ast.parse(file_path.read_text(encoding="utf-8"), filename=str(file_path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                names = [t.id for t in node.targets if isinstance(t, ast.Name)]
                if not names or not any(_looks_like_policy_name(n) for n in names):
                    continue
                if isinstance(node.value, ast.Constant) and isinstance(node.value.value, (int, float)):
                    rendered = f"{names[0]}={node.value.value!r}"
                    snippets.append(NumericSnippet(module_name, _fp(rendered), rendered))
                    if not _is_allowed(module_name):
                        violations.append(ArchitectureViolation("CANON_POLICY_LEAKAGE", f"Policy-like numeric snippet outside semantic owner: {rendered}", module_name))

    by_fp: dict[str, list[NumericSnippet]] = {}
    for s in snippets:
        by_fp.setdefault(s.fingerprint, []).append(s)
    for fp, refs in by_fp.items():
        mods = {r.module_name for r in refs}
        if len(mods) > 1 and len(refs) > 1:
            violations.append(ArchitectureViolation("CANON_POLICY_DUPLICATION", f"Duplicated policy-like numeric snippet across modules: {sorted(mods)} :: example={refs[0].rendered}", fp))
    return violations
