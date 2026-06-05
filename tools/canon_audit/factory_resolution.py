from __future__ import annotations

from dataclasses import dataclass
from typing import List

from tools.canon_audit.constructor_flow import ConstructorEdge
from tools.canon_audit.contracts import ArchitectureViolation

MARKERS = ("factory", "builder", "provider", "registry", "container", "resolver", "service_locator")


def scan_factory_resolution_risks(constructor_edges: list[ConstructorEdge]) -> list[ArchitectureViolation]:
    violations: list[ArchitectureViolation] = []
    for edge in constructor_edges:
        lowered_scope = edge.caller_scope.lower()
        lowered_target = edge.target_ref.lower()
        if any(m in lowered_scope or m in lowered_target for m in MARKERS):
            violations.append(ArchitectureViolation("CANON_FACTORY_RESOLUTION_RISK", f"Factory/provider/container-like constructor flow detected: {edge.caller_module}:{edge.caller_scope} -> {edge.target_ref}", edge.caller_module))
    return violations
