from __future__ import annotations

"""Canonical CEO runtime facade.

The package is itself the stable public surface. Historical imports through
``runtime.ceo.public_api`` are preserved via an explicit compat module so we do not keep
an extra re-export file around.
"""

from dataclasses import dataclass
from typing import Any
from collections.abc import Iterable, Mapping

from core.actions import build_schema_registry
from runtime.actions import ACTION_EXECUTE_PLAN_V1
from runtime.application.contracts import build_runtime_application_service_from_raw
from runtime.boot.actions_registry import get_spec
from runtime.boot.builders.ai_ceo_planner import build_runtime_ai_ceo_planner

CANON_RUNTIME_CEO_PUBLIC_API = True


@dataclass(frozen=True)
class CEOExecutionEnvelope:
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
    used_planner = planner or build_runtime_ai_ceo_planner(event_store=event_store)
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


def execute_strategy(
    plan: Any,
    *,
    user_id: str,
    decision_core: Any | None = None,
    observability: Any | None = None,
) -> CEOExecutionEnvelope | dict[str, Any]:
    envelope = _build_execute_plan_envelope(plan=plan, user_id=user_id)
    if decision_core is None:
        return envelope
    service = build_runtime_application_service_from_raw(
        decision_core=decision_core,
        observability=observability,
    )
    return service.execute_action({"action": envelope.action, **dict(envelope.payload)})


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
    )
    return plan, result


def _build_execute_plan_envelope(*, plan: Any, user_id: str) -> CEOExecutionEnvelope:
    steps = list(getattr(plan, "steps", []) or [])
    _validate_plan_steps(steps)
    payload = {
        "user_id": str(user_id),
        "steps": [_normalize_step(step) for step in steps],
    }
    build_schema_registry().validate(ACTION_EXECUTE_PLAN_V1, payload)
    get_spec(ACTION_EXECUTE_PLAN_V1)
    return CEOExecutionEnvelope(action=ACTION_EXECUTE_PLAN_V1, payload=payload)


def _validate_plan_steps(steps: Iterable[Any]) -> None:
    schema_registry = build_schema_registry()
    for step in steps:
        normalized = _normalize_step(step)
        action_name = str(normalized.get("action") or "")
        get_spec(action_name)
        schema_registry.validate(action_name, dict(normalized.get("payload") or {}))


def _normalize_step(step: Any) -> dict[str, Any]:
    if isinstance(step, Mapping):
        action = str(step.get("action") or "")
        payload = dict(step.get("payload") or {})
        return {"action": action, "payload": payload}
    action = str(getattr(step, "action", "") or "")
    payload = dict(getattr(step, "payload", {}) or {})
    return {"action": action, "payload": payload}




__all__ = [
    "CANON_RUNTIME_CEO_PUBLIC_API",
    "CEOExecutionEnvelope",
    "execute_strategy",
    "generate_plan",
    "run_ceo_cycle",
]


