from __future__ import annotations

import logging

from runtime.execution.entrypoint_context import run_with_bound_execution_context
from runtime.execution.executor_commit import _decision_tenant_id, has_pending
from runtime.execution.executor_result import ExecutionResult
from runtime.execution.outcome_persistence_lock import finalize_recovered_outcome
from runtime.observability.perf import watchdog_tick
from runtime.proofs import ACTION_PROOF_EVENT

logger = logging.getLogger(__name__)


def _record_recovery_trace(*, executor, env, stage: str, **fields: object) -> None:
    observability = getattr(executor, "_runtime_observability", None)
    method = getattr(observability, "record_recovery_trace", None) if observability is not None else None
    if not callable(method):
        return
    payload = {k: v for k, v in dict(fields).items() if isinstance(v, str | int | float)}
    payload.setdefault("decision_id", str(getattr(getattr(env, "decision", None), "decision_id", "") or ""))
    payload.setdefault("action", str(getattr(getattr(env, "decision", None), "action", "") or ""))
    generated_at_ms = 0
    decision_payload = getattr(getattr(env, "decision", None), "payload", {}) or {}
    if isinstance(decision_payload, dict):
        try:
            generated_at_ms = int(decision_payload.get("generated_at_ms") or decision_payload.get("now_ms") or 0)
        except (TypeError, ValueError, OverflowError):
            generated_at_ms = 0
    try:
        method(trace_name="runtime_recovery", stage=stage, generated_at_ms=generated_at_ms, **payload)
    except Exception:
        logger.debug("runtime_recovery: trace emission failed", exc_info=True)


def _append_recovery_checkpoint(reliability, env, *, stage: str, checkpoint_id: str, payload: dict[str, object]) -> None:
    if reliability is None:
        return
    reliability.append_checkpoint(
        env,
        stage=stage,
        checkpoint_id=checkpoint_id,
        payload=payload,
    )


def _record_recovery_failure(reliability, env, *, reason: str, primary_error: Exception) -> None:
    if reliability is None:
        return
    operations = (
        ("mark_failed", lambda: reliability.mark_failed(env, reason=reason)),
        (
            "append_checkpoint:failed",
            lambda: reliability.append_checkpoint(
                env,
                stage="failed",
                checkpoint_id=f"failed:{env.decision.decision_id}",
                payload={"recovery": "dispatch_failed", "reason": reason.removeprefix("recovery_dispatch:")},
            ),
        ),
    )
    # The dispatch error remains the primary failure. Persistence errors are
    # attached as notes and logged, never allowed to turn a failed dispatch into
    # success or to mask the original exception.
    for operation, fn in operations:
        try:
            fn()
        except Exception as persistence_error:  # documented failure-recording boundary
            logger.error("runtime_recovery: reliability operation failed: %s", operation, exc_info=persistence_error)
            if hasattr(primary_error, "add_note"):
                primary_error.add_note(
                    f"recovery persistence failed during {operation}: "
                    f"{type(persistence_error).__name__}: {persistence_error}"
                )


def has_proof_event(*, event_log, decision_id: str, action: str, warn) -> bool:
    del warn  # retained for compatibility with the public recovery entrypoint
    expected_event = ACTION_PROOF_EVENT.get(str(action))
    if not expected_event or event_log is None or not hasattr(event_log, "has_event"):
        return False
    # A lookup failure is not evidence that the proof is absent. Propagate it so
    # recovery cannot re-dispatch an irreversible effect on a false negative.
    return bool(event_log.has_event(str(decision_id), expected_event))


def execute_recovery_flow(*, executor, env, outbox, guard, event_log, executor_context_cm, warn) -> ExecutionResult:
    reliability = getattr(executor, "_reliability", None)
    _append_recovery_checkpoint(
        reliability,
        env,
        stage="recovery",
        checkpoint_id=f"recovery:{env.decision.decision_id}",
        payload={"mode": "execute_recovery"},
    )
    _record_recovery_trace(executor=executor, env=env, stage="started")
    if outbox is None:
        raise RuntimeError("RECOVERY_REQUIRES_OUTBOX")
    tenant_id = _decision_tenant_id(env.decision)
    if not has_pending(outbox, decision_id=str(env.decision.decision_id), tenant_id=tenant_id):
        raise RuntimeError("RECOVERY_REQUIRES_PENDING_OUTBOX")

    guard.verify_recovery(env)

    recovered = executor._mark_delivered_if_already_executed(env)
    if recovered is not None:
        # _mark_delivered_if_already_executed delegates to the canonical outcome
        # persistence owner, which already marks completion and appends the
        # completed checkpoint. Do not duplicate those writes here.
        _record_recovery_trace(executor=executor, env=env, stage="already_executed")
        return recovered
    if has_proof_event(
        event_log=event_log,
        decision_id=str(env.decision.decision_id),
        action=str(env.decision.action),
        warn=warn,
    ):
        persistence = finalize_recovered_outcome(
            executor=executor,
            env=env,
            reason="has_proof_event",
            backend_name="runtime_recovery_from_proof",
        )
        _record_recovery_trace(executor=executor, env=env, stage="proof_finalized", persistence_owner=str(persistence.get("state_update", {}).get("owner", "")))
        return ExecutionResult(
            ok=True,
            output={"status": "already_executed", "recovery": "marked_delivered", "persistence": persistence},
            decision_id=str(env.decision.decision_id),
            correlation_id=str(env.decision.correlation_id),
        )

    watchdog_tick(event_log)
    try:
        result = run_with_bound_execution_context(
            env=env,
            executor_context_cm=executor_context_cm,
            context_name="RuntimeExecutor.execute_recovery",
            run=lambda: executor._dispatch(env, depth=0, enqueue=False),
        )
        _record_recovery_trace(executor=executor, env=env, stage="resumed", ok=1 if getattr(result, "ok", False) else 0)
        return result
    except Exception as exc:
        exc_name = type(exc).__name__
        _record_recovery_failure(
            reliability,
            env,
            reason=f"recovery_dispatch:{exc_name}",
            primary_error=exc,
        )
        _record_recovery_trace(executor=executor, env=env, stage="failed", error=exc_name)
        raise
