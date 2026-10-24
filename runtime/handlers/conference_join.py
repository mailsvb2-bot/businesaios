from __future__ import annotations

from typing import Any

from runtime.handler_impl.core.payloads import require_mapping, required_str
from runtime.ports.effects import EffectsPort

CANON_THIN_HANDLER = True


def handle_run_conference_join_plan(payload: dict[str, Any], effects: EffectsPort, env: Any) -> Any:
    body = require_mapping(payload)
    plan = body.get("plan")
    if not isinstance(plan, list):
        raise ValueError("plan is required")
    return effects.run_conference_join_plan(decision_id=str(env.decision.decision_id),
                                            correlation_id=str(env.decision.correlation_id),
                                            tenant_id=required_str(body, "tenant_id"), user_id=required_str(body, "user_id"),
                                            plan=plan, integration_id=required_str(body, "integration_id"))


__all__ = ["handle_run_conference_join_plan"]
