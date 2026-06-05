from __future__ import annotations

import ast
from collections.abc import Sequence
from pathlib import Path

from canon.trace_contracts import CANONICAL_TRACE_STAGES
from tools.canon_audit.contracts import ArchitectureViolation
from tools.canon_audit.import_graph import collect_python_files, module_name_from_path


def scan_trace_contracts(
    root: Path, include_paths: Sequence[str] | None = None
) -> list[ArchitectureViolation]:
    violations: list[ArchitectureViolation] = []
    required = set(CANONICAL_TRACE_STAGES)
    for file_path in collect_python_files(root, include_paths=include_paths):
        module_name = module_name_from_path(root, file_path)
        if "trace" not in module_name and "contract" not in module_name and "execution" not in module_name:
            continue
        text = file_path.read_text(encoding="utf-8")
        lowered = text.lower()
        mentioned = {stage for stage in required if stage in lowered}
        trace_module = (
            "trace" in module_name
            or "trace_contract" in module_name
            or "execution_trace" in module_name
        )
        if trace_module and len(mentioned) < 4:
            violations.append(
                ArchitectureViolation(
                    "CANON_TRACE_CONTRACT_WEAK",
                    f"Trace/contract module references too few canonical stages: {sorted(mentioned)}",
                    module_name,
                )
            )
        tree = ast.parse(text, filename=str(file_path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Assign):
                continue
            for target in node.targets:
                if not isinstance(target, ast.Name):
                    continue
                if "trace" not in target.id.lower() or not isinstance(node.value, ast.List | ast.Tuple):
                    continue
                elts = [
                    elt.value.lower()
                    for elt in node.value.elts
                    if isinstance(elt, ast.Constant) and isinstance(elt.value, str)
                ]
                if not elts:
                    continue
                missing = required - set(elts)
                if missing:
                    violations.append(
                        ArchitectureViolation(
                            "CANON_TRACE_CONTRACT_MISSING_STAGE",
                            f"Declared trace list misses canonical stages: {sorted(missing)}",
                            module_name,
                        )
                    )
    return violations
