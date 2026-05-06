from __future__ import annotations

from typing import List

from tools.canon_audit.constructor_flow import ConstructorEdge
from tools.canon_audit.contracts import ArchitectureViolation


def scan_provider_wiring(constructor_edges: List[ConstructorEdge]) -> List[ArchitectureViolation]:
    violations: List[ArchitectureViolation] = []
    for edge in constructor_edges:
        caller = edge.caller_module
        target = edge.target_ref.split(":")[0]
        if caller.startswith("application.decision") or caller.startswith("application.policy"):
            if target.startswith("runtime._internal") or target.startswith("runtime.execution"):
                violations.append(ArchitectureViolation("CANON_PROVIDER_WIRING_DECISION_RUNTIME", f"Decision/policy wiring runtime provider into semantic owner: {caller}:{edge.caller_scope} -> {edge.target_ref}", caller))
        if caller.startswith("interfaces.") or caller.startswith("entrypoints."):
            if target.startswith("runtime._internal"):
                violations.append(ArchitectureViolation("CANON_PROVIDER_WIRING_ENTRYPOINT_EFFECT", f"Entrypoint wiring effect provider directly: {caller}:{edge.caller_scope} -> {edge.target_ref}", caller))
        if caller.startswith("runtime._internal") and target.startswith("application.decision"):
            violations.append(ArchitectureViolation("CANON_PROVIDER_WIRING_EFFECT_DECISION", f"Sealed effect zone wiring decision owner directly: {caller}:{edge.caller_scope} -> {edge.target_ref}", caller))
    return violations
