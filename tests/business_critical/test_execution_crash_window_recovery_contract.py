from __future__ import annotations

from runtime.execution.crash_window_recovery_contract import (
    CrashWindowRecoveryAction,
    ExecutionCrashWindowState,
    required_recovery_action,
)


def test_ledger_marked_before_dispatch_must_replay_dispatch() -> None:
    state = ExecutionCrashWindowState(
        decision_id="decision-1",
        idempotency_key="idem-1",
        ledger_marked=True,
        dispatch_claimed=False,
        handler_dispatched=False,
        effect_verified=False,
    )

    assert required_recovery_action(state) == CrashWindowRecoveryAction.REPLAY_DISPATCH


def test_dispatched_but_unverified_must_verify_or_retry() -> None:
    state = ExecutionCrashWindowState(
        decision_id="decision-1",
        idempotency_key="idem-1",
        ledger_marked=True,
        dispatch_claimed=True,
        handler_dispatched=True,
        effect_verified=False,
    )

    assert required_recovery_action(state) == CrashWindowRecoveryAction.VERIFY_OR_RETRY_DISPATCH


def test_verified_effect_is_not_replayed() -> None:
    state = ExecutionCrashWindowState(
        decision_id="decision-1",
        idempotency_key="idem-1",
        ledger_marked=True,
        dispatch_claimed=True,
        handler_dispatched=True,
        effect_verified=True,
    )

    assert required_recovery_action(state) == CrashWindowRecoveryAction.NOOP_ALREADY_VERIFIED


def test_invalid_execution_state_is_blocked() -> None:
    state = ExecutionCrashWindowState(
        decision_id="decision-1",
        idempotency_key="idem-1",
        ledger_marked=False,
        dispatch_claimed=True,
        handler_dispatched=False,
        effect_verified=False,
    )

    assert required_recovery_action(state) == CrashWindowRecoveryAction.BLOCK_INVALID_STATE
