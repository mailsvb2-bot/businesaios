from __future__ import annotations

from dataclasses import dataclass

from tools.canon_audit.call_graph import CallEdge
from tools.canon_audit.contracts import ArchitectureViolation


@dataclass(frozen=True)
class RouteExpectation:
    caller_prefix: str
    forbidden_callee_prefixes: tuple[str, ...]
    label: str


ROUTE_EXPECTATIONS = (
    RouteExpectation("interfaces", ("runtime.execution", "runtime._internal"), "entrypoints_must_not_jump_to_runtime"),
    RouteExpectation("application.decision", ("runtime._internal",), "decision_must_not_call_effects"),
    RouteExpectation("runtime.execution", ("application.decision",), "executor_must_not_decide"),
)


def scan_route_expectations(edges: list[CallEdge]) -> list[ArchitectureViolation]:
    violations: list[ArchitectureViolation] = []
    for edge in edges:
        caller_module = edge.caller_fqname.split(":")[0]
        callee_module = edge.callee_ref.split(":")[0]
        for spec in ROUTE_EXPECTATIONS:
            caller_matches = caller_module == spec.caller_prefix or caller_module.startswith(
                spec.caller_prefix + "."
            )
            callee_forbidden = any(
                callee_module == prefix or callee_module.startswith(prefix + ".")
                for prefix in spec.forbidden_callee_prefixes
            )
            if caller_matches and callee_forbidden:
                violations.append(
                    ArchitectureViolation(
                        "CANON_ROUTE_FORBIDDEN_CALL",
                        f"Route violation [{spec.label}]: {edge.caller_fqname} -> {edge.callee_ref}",
                        caller_module,
                    )
                )
    return violations
