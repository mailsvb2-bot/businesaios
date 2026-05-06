from __future__ import annotations

CANONICAL_EXECUTION_PATH: tuple[str, ...] = (
    "request",
    "world_state",
    "decision",
    "action_plan",
    "executor",
    "verification",
    "world_state_update",
    "evidence",
    "memory",
    "next_context",
)

CANONICAL_ROUTE_OWNERS: tuple[str, ...] = (
    "interfaces",
    "application.world_state",
    "application.decision",
    "application.decision",
    "runtime.execution",
    "application.evidence",
    "application.world_state",
    "application.evidence",
    "application.memory",
    "application.headless",
)

__all__ = ["CANONICAL_EXECUTION_PATH", "CANONICAL_ROUTE_OWNERS"]
