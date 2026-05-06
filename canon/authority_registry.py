from __future__ import annotations

from enum import Enum


class CanonAuthority(str, Enum):
    DECISION = "decision"
    WORLD_STATE = "world_state"
    EXECUTION = "execution"
    EFFECT = "effect"
    EVIDENCE = "evidence"
    MEMORY = "memory"
    APPROVAL = "approval"
    BUDGET = "budget"
    KILL_SWITCH = "kill_switch"
    CAPABILITY_VERDICT = "capability_verdict"


CANONICAL_AUTHORITY_OWNERS: dict[CanonAuthority, str] = {
    CanonAuthority.DECISION: "application.decision",
    CanonAuthority.WORLD_STATE: "application.world_state",
    CanonAuthority.EXECUTION: "runtime.execution",
    CanonAuthority.EFFECT: "runtime._internal",
    CanonAuthority.EVIDENCE: "application.evidence",
    CanonAuthority.MEMORY: "application.memory",
    CanonAuthority.APPROVAL: "application.governance",
    CanonAuthority.BUDGET: "application.governance",
    CanonAuthority.KILL_SWITCH: "application.governance",
    CanonAuthority.CAPABILITY_VERDICT: "application.capability",
}


__all__ = ["CanonAuthority", "CANONICAL_AUTHORITY_OWNERS"]
