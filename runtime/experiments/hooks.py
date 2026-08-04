from __future__ import annotations

import logging
import time
from collections.abc import Mapping
from types import SimpleNamespace
from typing import Any

from core.experiments.guardrails import CanaryDecision, GuardrailResult
from core.experiments.live_canary_events import LIVE_CANARY_EXECUTION_FAILED_SOURCE
from runtime.experiments.cost_semantics import resolve_execution_cost
from runtime.experiments.live_canary import source_event_evidence_ref
from runtime.experiments.proof_semantics import resolve_action_proof_success
from runtime.proofs import ACTION_PROOF_EVENT

log = logging.getLogger(__name__)


def _coordinator(decision_core: Any) -> Any | None:
    return getattr(decision_core, "_live_canary", None)


def _safe_mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _event_data(event: Any) -> dict[str, Any]:
    if isinstance(event, Mapping):
        return dict(event)
    return dict(getattr(event, "__dict__", {}))


def _source_proof_event(
    coordinator: Any,
    *,
    decision_id: str,
    proof_event_type: str,
    ok: bool,
) -> Any:
    events = coordinator.ledger.events_for_decision(
        str(decision_id),
        str(proof_event_type),
    )
    for event in reversed(events):
        data = _event_data(event)
        if str(data.get("source") or "") == "live_canary":
            continue
        payload = _safe_mapping(data.get("payload"))
        observed = resolve_action_proof_success(proof_event_type, payload)
        if observed is bool(ok):
            return event
    raise RuntimeError("LIVE_CANARY_VERIFIED_SOURCE_EVENT_REQUIRED")


def _force_rollback(
    coordinator: Any,
    *,
    executor: Any,
    decision_id: str,
    correlation_id: str | None,
    tenant_id: str,
    reason: str,
) -> None:
    result = GuardrailResult(
        CanaryDecision.ROLLBACK,
        (str(reason),),
        {},
    )
    coordinator._open_local_circuit(
        result,
        decision_id=str(decision_id),
        correlation_id=correlation_id,
        tenant_id=str(tenant_id),
    )
    kwargs = {
        "decision_id": str(decision_id),
        "correlation_id": correlation_id,
        "tenant_id": str(tenant_id),
        "candidate_policy_id": coordinator.candidate_policy_id,
        "experiment_id": coordinator.policy.experiment_id,
        "reasons": result.reasons,
    }
    submitter = getattr(executor, "_live_canary_rollback_submitter", None)
    if not callable(submitter):
        submitter = getattr(
            getattr(executor, "_decision_core", None),
            "_live_canary_rollback_submitter",
            None,
        )
    if not callable(submitter):
        submitter = getattr(executor, "submit_live_canary_rollback", None)
    if callable(submitter):
        submitter(**kwargs)
        return
    applied = coordinator.evaluate_and_maybe_rollback(
        decision_id=str(decision_id),
        correlation_id=correlation_id,
        tenant_id=str(tenant_id),
    )
    if applied.decision is not CanaryDecision.ROLLBACK:
        raise RuntimeError("LIVE_CANARY_ROLLBACK_NOT_APPLIED")


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
            ACTION_PROOF_EVENT.get(action)
            if ok
            else LIVE_CANARY_EXECUTION_FAILED_SOURCE
        )
        if not proof_event_type:
            _force_rollback(
                coordinator,
                executor=executor,
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
                    executor=executor,
                    decision_id=f"execution-integrity:{decision_id}",
                    correlation_id=correlation_id,
                    tenant_id=tenant_id,
                    reason="execution_failure_evidence_unavailable",
                )
                return

        proof_event = _source_proof_event(
            coordinator,
            decision_id=decision_id,
            proof_event_type=proof_event_type,
            ok=ok,
        )
        proof_payload = _safe_mapping(_event_data(proof_event).get("payload"))
        payload = _safe_mapping(getattr(decision, "payload", None))
        if output.get("_live_canary_actual_cost_missing") is True:
            raise RuntimeError("LIVE_CANARY_EXECUTION_COST_EVIDENCE_REQUIRED")
        coordinator.record_execution(
            decision_id=decision_id,
            correlation_id=correlation_id,
            arm=str(assignment.get("arm") or ""),
            action=action,
            ok=ok,
            cost=resolve_execution_cost(
                result_output=output,
                proof_payload=proof_payload,
                expected_cost=payload.get("expected_cost"),
            ),
            proof_event_type=proof_event_type,
            evidence_ref=source_event_evidence_ref(proof_event),
            critical_violation=bool(output.get("critical_violation")),
            complaint=bool(output.get("complaint")),
            executed_at_ms=int(time.time() * 1000),
        )
        guard = coordinator._guard_result()
        if guard.decision is CanaryDecision.ROLLBACK:
            _force_rollback(
                coordinator,
                executor=executor,
                decision_id=f"execution-guard:{decision_id}",
                correlation_id=correlation_id,
                tenant_id=tenant_id,
                reason="execution_guard:" + ",".join(guard.reasons),
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
                executor=executor,
                decision_id=f"execution-integrity:{decision_id}",
                correlation_id=correlation_id,
                tenant_id=tenant_id,
                reason=f"execution_evidence_error:{type(exc).__name__}",
            )
        except Exception:
            log.exception("live_canary_executor_evidence_rollback_failed")


def record_live_canary_executor_exception(
    *,
    executor: Any,
    env: Any,
    exc: BaseException,
) -> None:
    """Record fail-closed canary evidence while preserving the original exception."""

    result = SimpleNamespace(
        ok=False,
        output={
            "exception_type": type(exc).__name__,
            "message": str(exc),
            "critical_violation": False,
            "complaint": False,
            "_live_canary_actual_cost_missing": True,
        },
        error=f"{type(exc).__name__}: {exc}",
    )
    record_live_canary_executor_result(
        executor=executor,
        env=env,
        result=result,
    )


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
    "record_live_canary_executor_exception",
    "record_live_canary_executor_result",
]
