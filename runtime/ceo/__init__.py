"""Canonical CEO runtime facade.

The package is itself the stable public surface. Historical imports through
``runtime.ceo.public_api`` are preserved via an explicit compat module so we do
not keep an extra re-export file around.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any

from core.actions import build_schema_registry
from runtime.actions import ACTION_EXECUTE_PLAN_V1
from runtime.application.contracts import (
    build_runtime_application_service_from_raw,
)
from runtime.boot.actions_registry import get_spec
from runtime.boot.builders.ai_ceo_planner import build_runtime_ai_ceo_planner

CANON_RUNTIME_CEO_PUBLIC_API = True
CANON_RUNTIME_CEO_EXECUTION_REQUIRES_ISSUED_ENVELOPE = True


@dataclass(frozen=True)
class CEOExecutionEnvelope:
    """Validated execute-plan proposal, not a DecisionEnvelope."""

    action: str
    payload: dict[str, Any]


def generate_plan(
    *,
    tenant_id: str,
    objective: str,
    horizon: str,
    decision_id: str,
    correlation_id: str,
    event_store: Any | None = None,
    planner: Any | None = None,
):
    used_planner = planner or build_runtime_ai_ceo_planner(
        event_store=event_store
    )
    build_plan = getattr(used_planner, "build_plan", None)
    if not callable(build_plan):
        raise TypeError("planner must expose build_plan")
    return build_plan(
        tenant_id=tenant_id,
        objective=objective,
        horizon=horizon,
        decision_id=decision_id,
        correlation_id=correlation_id,
    )


def _validate_issued_envelope_matches_proposal(
    *,
    decision_envelope: Any,
    proposal: CEOExecutionEnvelope,
) -> None:
    decision = getattr(decision_envelope, "decision", None)
    if decision is None:
        raise TypeError("canonical DecisionEnvelope required")
    if not str(getattr(decision, "decision_id", "") or "").strip():
        raise TypeError("DecisionEnvelope decision_id required")
    if not str(
        getattr(decision, "correlation_id", "") or ""
    ).strip():
        raise TypeError("DecisionEnvelope correlation_id required")
    if str(getattr(decision, "action", "") or "") != proposal.action:
        raise ValueError("DecisionEnvelope action does not match CEO proposal")
    issued_payload = dict(getattr(decision, "payload", {}) or {})
    if issued_payload != proposal.payload:
        raise ValueError("DecisionEnvelope payload does not match CEO proposal")


def execute_strategy(
    plan: Any,
    *,
    user_id: str,
    decision_core: Any | None = None,
    observability: Any | None = None,
    decision_envelope: Any | None = None,
) -> CEOExecutionEnvelope | dict[str, Any]:
    """Build a proposal or execute an already-issued matching envelope.

    ``decision_core`` is retained as a historical keyword, but in this execution
    surface it must be the execution-only owner exposing ``execute(envelope)``.
    The sovereign DecisionCore must issue ``decision_envelope`` elsewhere via the
    canonical runtime gateway.
    """

    proposal = _build_execute_plan_envelope(plan=plan, user_id=user_id)
    if decision_core is None and decision_envelope is None:
        return proposal
    if decision_core is None or decision_envelope is None:
        raise TypeError(
            "CEO execution requires both decision_envelope and "
            "an execution-only owner"
        )

    _validate_issued_envelope_matches_proposal(
        decision_envelope=decision_envelope,
        proposal=proposal,
    )
    service = build_runtime_application_service_from_raw(
        decision_core=decision_core,
        observability=observability,
    )
    return service.execute_action(decision_envelope)


def run_ceo_cycle(
    *,
    tenant_id: str,
    user_id: str,
    objective: str,
    horizon: str,
    decision_id: str,
    correlation_id: str,
    decision_core: Any | None = None,
    observability: Any | None = None,
    decision_envelope: Any | None = None,
    event_store: Any | None = None,
    planner: Any | None = None,
) -> tuple[Any, CEOExecutionEnvelope | dict[str, Any]]:
    plan = generate_plan(
        tenant_id=tenant_id,
        objective=objective,
        horizon=horizon,
        decision_id=decision_id,
        correlation_id=correlation_id,
        event_store=event_store,
        planner=planner,
    )
    result = execute_strategy(
        plan,
        user_id=user_id,
        decision_core=decision_core,
        observability=observability,
        decision_envelope=decision_envelope,
    )
    return plan, result


def _build_execute_plan_envelope(
    *,
    plan: Any,
    user_id: str,
) -> CEOExecutionEnvelope:
    steps = list(getattr(plan, "steps", []) or [])
    _validate_plan_steps(steps)
    payload = {
        "user_id": str(user_id),
        "steps": [_normalize_step(step) for step in steps],
    }
    build_schema_registry().validate(ACTION_EXECUTE_PLAN_V1, payload)
    get_spec(ACTION_EXECUTE_PLAN_V1)
    return CEOExecutionEnvelope(
        action=ACTION_EXECUTE_PLAN_V1,
        payload=payload,
    )


def _validate_plan_steps(steps: Iterable[Any]) -> None:
    schema_registry = build_schema_registry()
    for step in steps:
        normalized = _normalize_step(step)
        action_name = str(normalized.get("action") or "")
        get_spec(action_name)
        schema_registry.validate(
            action_name,
            dict(normalized.get("payload") or {}),
        )


def _normalize_step(step: Any) -> dict[str, Any]:
    if isinstance(step, Mapping):
        action = str(step.get("action") or "")
        payload = dict(step.get("payload") or {})
        return {"action": action, "payload": payload}
    action = str(getattr(step, "action", "") or "")
    payload = dict(getattr(step, "payload", {}) or {})
    return {"action": action, "payload": payload}


__all__ = [
    "CANON_RUNTIME_CEO_EXECUTION_REQUIRES_ISSUED_ENVELOPE",
    "CANON_RUNTIME_CEO_PUBLIC_API",
    "CEOExecutionEnvelope",
    "execute_strategy",
    "generate_plan",
    "run_ceo_cycle",
]
