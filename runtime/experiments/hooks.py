from __future__ import annotations

import logging
import math
import time
from collections.abc import Mapping
from typing import Any

from core.actions.proof_registry import ACTION_PROOF_EVENT
from core.experiments.live_canary_events import (
    CANARY_AUTO_ROLLED_BACK,
    CANARY_GUARDRAIL_BREACHED,
)

log = logging.getLogger(__name__)
_EXECUTION_FAILURE_SOURCE = "live_canary_execution_failed_source@v1"


def _coordinator(decision_core: Any) -> Any | None:
    return getattr(decision_core, "_live_canary", None)


def _safe_mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _finite(value: object, default: float = 0.0) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    return number if math.isfinite(number) else default


def _force_rollback(
    coordinator: Any,
    *,
    decision_id: str,
    correlation_id: str | None,
    tenant_id: str,
    reason: str,
) -> None:
    from_pct = coordinator.live_rollout_pct()
    payload = {
        "tenant_id": str(tenant_id),
        "experiment_id": coordinator.policy.experiment_id,
        "candidate_policy_id": coordinator.candidate_policy_id,
        "reasons": [str(reason)],
        "metrics": {},
    }
    snapshot = coordinator.policy_registry.snapshot_runtime_state()
    try:
        coordinator.policy_registry.set_rollout(
            candidate_policy_id=coordinator.candidate_policy_id,
            rollout_pct=0,
        )
    except Exception:
        coordinator.policy_registry.restore_runtime_state(snapshot)
        raise
    coordinator._rollback_required = False
    try:
        coordinator.event_log.emit(
            event_type=CANARY_GUARDRAIL_BREACHED,
            source="live_canary",
            user_id="system",
            decision_id=str(decision_id),
            correlation_id=correlation_id,
            payload=payload,
        )
        coordinator.event_log.emit(
            event_type=CANARY_AUTO_ROLLED_BACK,
            source="live_canary",
            user_id="system",
            decision_id=str(decision_id),
            correlation_id=correlation_id,
            payload={**payload, "from_pct": from_pct, "to_pct": 0},
        )
    except Exception:
        log.exception("live_canary_rollback_audit_failed")


def record_live_canary_executor_result(
    *,
    executor: Any,
    env: Any,
    result: Any,
) -> None:
    """Record real executor evidence without ever masking the execution result."""

    coordinator = _coordinator(getattr(executor, "_decision_core", None))
    if coordinator is None:
        return
    try:
        decision = getattr(env, "decision", None)
        decision_id = str(getattr(decision, "decision_id", "") or "")
        assignment = coordinator.ledger.assignment_for_decision(decision_id)
        if assignment is None or assignment.get("eligible") is not True:
            return

        correlation_id = str(getattr(decision, "correlation_id", "") or "") or None
        tenant_id = str(assignment.get("tenant_id") or "")
        action = str(getattr(decision, "action", "") or "")
        ok = bool(getattr(result, "ok", False))
        output = _safe_mapping(getattr(result, "output", None))
        proof_event_type = (
            ACTION_PROOF_EVENT.get(action) if ok else _EXECUTION_FAILURE_SOURCE
        )
        if not proof_event_type:
            _force_rollback(
                coordinator,
                decision_id=f"execution-integrity:{decision_id}",
                correlation_id=correlation_id,
                tenant_id=tenant_id,
                reason="missing_action_proof_contract",
            )
            return

        if not ok:
            try:
                coordinator.event_log.emit(
                    event_type=proof_event_type,
                    source="runtime_executor",
                    user_id="system",
                    decision_id=decision_id,
                    correlation_id=correlation_id,
                    payload={
                        "ok": False,
                        "error": str(getattr(result, "error", "") or ""),
                        "output": output,
                    },
                )
            except Exception:
                _force_rollback(
                    coordinator,
                    decision_id=f"execution-integrity:{decision_id}",
                    correlation_id=correlation_id,
                    tenant_id=tenant_id,
                    reason="execution_failure_evidence_unavailable",
                )
                return

        payload = _safe_mapping(getattr(decision, "payload", None))
        coordinator.record_execution(
            decision_id=decision_id,
            correlation_id=correlation_id,
            arm=str(assignment.get("arm") or ""),
            action=action,
            ok=ok,
            cost=max(
                _finite(payload.get("expected_cost")),
                _finite(output.get("cost", output.get("actual_cost"))),
            ),
            proof_event_type=proof_event_type,
            evidence_ref=f"runtime-execution:{decision_id}",
            critical_violation=bool(output.get("critical_violation")),
            complaint=bool(output.get("complaint")),
            executed_at_ms=int(time.time() * 1000),
        )
        coordinator.evaluate_and_maybe_rollback(
            decision_id=f"execution-guard:{decision_id}",
            correlation_id=correlation_id,
            tenant_id=tenant_id,
        )
    except Exception as exc:
        try:
            assignment = coordinator.ledger.assignment_for_decision(
                str(getattr(getattr(env, "decision", None), "decision_id", "") or "")
            )
            tenant_id = str((assignment or {}).get("tenant_id") or "")
            decision_id = str(
                getattr(getattr(env, "decision", None), "decision_id", "") or ""
            )
            correlation_id = (
                str(
                    getattr(
                        getattr(env, "decision", None),
                        "correlation_id",
                        "",
                    )
                    or ""
                )
                or None
            )
            _force_rollback(
                coordinator,
                decision_id=f"execution-integrity:{decision_id}",
                correlation_id=correlation_id,
                tenant_id=tenant_id,
                reason=f"execution_evidence_error:{type(exc).__name__}",
            )
        except Exception:
            log.exception("live_canary_executor_evidence_rollback_failed")


def record_live_canary_business_outcome(
    *,
    decision_core: Any,
    decision_id: str,
    correlation_id: str | None,
    outcome_type: str,
    success: bool,
    evidence_ref: str,
    observed_at_ms: int | None = None,
) -> dict[str, Any] | None:
    """Bind an already stored webhook/domain outcome to its canary assignment."""

    coordinator = _coordinator(decision_core)
    if coordinator is None:
        return None
    assignment = coordinator.ledger.assignment_for_decision(str(decision_id))
    if assignment is None or assignment.get("eligible") is not True:
        return None
    return coordinator.record_outcome(
        decision_id=str(decision_id),
        correlation_id=correlation_id,
        arm=str(assignment.get("arm") or ""),
        outcome_type=str(outcome_type),
        success=bool(success),
        evidence_ref=str(evidence_ref),
        observed_at_ms=observed_at_ms,
    )


__all__ = [
    "record_live_canary_business_outcome",
    "record_live_canary_executor_result",
]
