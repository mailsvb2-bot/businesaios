"""Crash-recovery helpers for RuntimeExecutor.

If action is not in ACTION_PROOF_EVENT, ``finalize_if_already_executed`` returns
``None`` and recovery proceeds to re-dispatch. Handlers must remain idempotent
for such actions.
"""

from __future__ import annotations

from typing import Any
from runtime.execution.executor_commit import _decision_tenant_id, status
from runtime.execution.executor_result import ExecutionResult
from runtime.execution.outcome_persistence_lock import finalize_recovered_outcome
from runtime.proofs import ACTION_PROOF_EVENT

def finalize_if_already_executed(*, executor: Any, outbox: Any, event_log: Any, env: Any) -> ExecutionResult | None:
    decision_id = str(env.decision.decision_id)
    action = str(env.decision.action)
    expected_event = ACTION_PROOF_EVENT.get(action)
    tenant_id = _decision_tenant_id(env.decision)
    current_status = status(outbox, decision_id=decision_id, tenant_id=tenant_id)

    if expected_event and current_status in {"pending", "delivering", "inflight"} and event_log is not None:
        if hasattr(event_log, "has_event") and event_log.has_event(decision_id, expected_event):
            persistence = finalize_recovered_outcome(
                executor=executor,
                env=env,
                reason="finalize_if_already_executed",
                backend_name="runtime_recovery_from_proof",
            )
            return ExecutionResult(
                ok=True,
                output={"status": "already_executed", "recovery": "marked_delivered", "persistence": persistence},
                decision_id=decision_id,
                correlation_id=env.decision.correlation_id,
            )
    return None
