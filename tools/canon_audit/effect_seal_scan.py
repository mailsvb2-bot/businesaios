from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import List

from canon.sealed_effect_policy import EFFECT_LITERAL_MARKERS, SEALED_EFFECT_PREFIXES
from tools.canon_audit.contracts import ArchitectureViolation
from tools.canon_audit.import_graph import collect_python_files, module_name_from_path


def _is_sealed(module_name: str) -> bool:
    return any(module_name == p or module_name.startswith(p + ".") for p in SEALED_EFFECT_PREFIXES)


def scan_effect_literals_outside_seal(root: Path, include_paths: Sequence[str] | None = None) -> list[ArchitectureViolation]:
    violations: list[ArchitectureViolation] = []
    for file_path in collect_python_files(root, include_paths=include_paths):
        module_name = module_name_from_path(root, file_path)
        if _is_sealed(module_name):
            continue
        text = file_path.read_text(encoding="utf-8", errors="ignore").lower()
        hits = [marker for marker in EFFECT_LITERAL_MARKERS if marker in text]
        if hits:
            violations.append(ArchitectureViolation("CANON_EFFECT_LITERAL_OUTSIDE_SEAL", f"Effect/API literal markers outside sealed zone: {sorted(set(hits))}", module_name))
    return violations
