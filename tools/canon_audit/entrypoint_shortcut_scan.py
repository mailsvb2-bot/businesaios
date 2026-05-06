from __future__ import annotations

from typing import List

from tools.canon_audit.call_graph import CallEdge
from tools.canon_audit.contracts import ArchitectureViolation


def scan_entrypoint_runtime_shortcuts(call_edges: List[CallEdge]) -> List[ArchitectureViolation]:
    violations: List[ArchitectureViolation] = []
    for edge in call_edges:
        caller_module = edge.caller_fqname.split(":")[0]
        callee_module = edge.callee_ref.split(":")[0]
        if caller_module.startswith("interfaces.") or caller_module.startswith("entrypoints."):
            if callee_module.startswith("runtime.execution") or callee_module.startswith("runtime._internal"):
                violations.append(ArchitectureViolation("CANON_ENTRYPOINT_RUNTIME_SHORTCUT", f"Entrypoint/runtime shortcut detected: {edge.caller_fqname} -> {edge.callee_ref}", caller_module))
    return violations
