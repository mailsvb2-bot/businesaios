from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class CrashWindowRecoveryAction(str, Enum):
    REPLAY_DISPATCH = "replay_dispatch"
    VERIFY_OR_RETRY_DISPATCH = "verify_or_retry_dispatch"
    NOOP_ALREADY_VERIFIED = "noop_already_verified"
    BLOCK_INVALID_STATE = "block_invalid_state"


@dataclass(frozen=True)
class ExecutionCrashWindowState:
    decision_id: str
    idempotency_key: str
    ledger_marked: bool
    dispatch_claimed: bool
    handler_dispatched: bool
    effect_verified: bool

    def validate(self) -> None:
        if not self.decision_id.strip():
            raise ValueError("decision_id_required")
        if not self.idempotency_key.strip():
            raise ValueError("idempotency_key_required")
        if self.effect_verified and not self.handler_dispatched:
            raise ValueError("verified_effect_requires_handler_dispatch")
        if self.handler_dispatched and not self.dispatch_claimed:
            raise ValueError("handler_dispatch_requires_claim")
        if self.dispatch_claimed and not self.ledger_marked:
            raise ValueError("dispatch_claim_requires_ledger_mark")


def required_recovery_action(state: ExecutionCrashWindowState) -> CrashWindowRecoveryAction:
    try:
        state.validate()
    except ValueError:
        return CrashWindowRecoveryAction.BLOCK_INVALID_STATE
    ledger_marked = bool(state.ledger_marked)
    effect_verified = bool(state.effect_verified)
    handler_dispatched = bool(state.handler_dispatched)
    if not ledger_marked:
        return CrashWindowRecoveryAction.BLOCK_INVALID_STATE
    if effect_verified:
        return CrashWindowRecoveryAction.NOOP_ALREADY_VERIFIED
    if handler_dispatched:
        return CrashWindowRecoveryAction.VERIFY_OR_RETRY_DISPATCH
    return CrashWindowRecoveryAction.REPLAY_DISPATCH


__all__ = ["CrashWindowRecoveryAction", "ExecutionCrashWindowState", "required_recovery_action"]
