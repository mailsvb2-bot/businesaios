"""Idempotency/ledger proof helpers for RuntimeGuard."""

from __future__ import annotations

import hashlib
from typing import Any


def mark_execution_once(*, ledger: Any, env: Any) -> None:
    try_mark = ledger.try_mark_executed
    if not bool(try_mark(env)):
        raise RuntimeError("DUPLICATE_EXECUTION")


def emit_ledger_executed(event_log: Any, *, env: Any) -> None:
    if event_log is None:
        return
    result_hash = hashlib.sha256((env.decision.decision_id + "|" + env.signature).encode("utf-8")).hexdigest()
    event_log.emit(
        event_type="ledger_executed",
        source="decision_ledger",
        user_id=env.decision.payload.get("user_id", "unknown") if isinstance(env.decision.payload, dict) else "unknown",
        decision_id=env.decision.decision_id,
        correlation_id=env.decision.correlation_id,
        payload={"result_hash": result_hash},
    )


def verify_idempotency_gate(*, ledger: Any, env: Any) -> None:
    """Compatibility surface for guard split locks.

    Fail closed when the ledger cannot answer execution status. This preserves the
    canonical runtime guard import surface without creating an alternate decision path.
    """
    is_executed = getattr(ledger, 'is_executed', None)
    if is_executed is None:
        raise RuntimeError('LEDGER_MISSING_EXECUTED_CHECK')
    if bool(is_executed(env.decision.decision_id)):
        raise RuntimeError('DUPLICATE_EXECUTION')
