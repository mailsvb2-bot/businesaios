from __future__ import annotations

from typing import List

from canon.authority_registry import CANONICAL_AUTHORITY_OWNERS, CanonAuthority
from tools.canon_audit.call_graph import CallEdge
from tools.canon_audit.contracts import ArchitectureViolation
from tools.canon_audit.registry import ManifestRegistry


def scan_owner_misuse(edges: list[CallEdge], registry: ManifestRegistry) -> list[ArchitectureViolation]:
    violations: list[ArchitectureViolation] = []

    decision_owner = CANONICAL_AUTHORITY_OWNERS[CanonAuthority.DECISION]
    effect_owner = CANONICAL_AUTHORITY_OWNERS[CanonAuthority.EFFECT]
    memory_owner = CANONICAL_AUTHORITY_OWNERS[CanonAuthority.MEMORY]
    evidence_owner = CANONICAL_AUTHORITY_OWNERS[CanonAuthority.EVIDENCE]

    for edge in edges:
        caller_module = edge.caller_fqname.split(":")[0]
        callee_module = edge.callee_ref.split(":")[0]

        if callee_module == decision_owner or callee_module.startswith(decision_owner + "."):
            if not (caller_module.startswith("application.decision") or caller_module.startswith("application.headless") or caller_module.startswith("application.execution")):
                violations.append(ArchitectureViolation("CANON_OWNER_MISUSE_DECISION", f"Non-canonical decision caller: {edge.caller_fqname} -> {edge.callee_ref}", caller_module))

        if callee_module == effect_owner or callee_module.startswith(effect_owner + "."):
            if not caller_module.startswith("runtime.execution"):
                violations.append(ArchitectureViolation("CANON_OWNER_MISUSE_EFFECT", f"Non-canonical effect caller: {edge.caller_fqname} -> {edge.callee_ref}", caller_module))

        if callee_module == memory_owner or callee_module.startswith(memory_owner + "."):
            if caller_module.startswith("interfaces.") or caller_module.startswith("runtime._internal."):
                violations.append(ArchitectureViolation("CANON_OWNER_MISUSE_MEMORY", f"Memory owner called from forbidden zone: {edge.caller_fqname} -> {edge.callee_ref}", caller_module))

        if callee_module == evidence_owner or callee_module.startswith(evidence_owner + "."):
            if caller_module.startswith("interfaces.") and not caller_module.startswith("interfaces.api"):
                violations.append(ArchitectureViolation("CANON_OWNER_MISUSE_EVIDENCE", f"Evidence owner called too early from interface zone: {edge.caller_fqname} -> {edge.callee_ref}", caller_module))
    return violations
