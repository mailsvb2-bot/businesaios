from __future__ import annotations

from typing import Any

from runtime.ads import AdsAutopilotConstraints, AdsAutopilotRequest
from runtime.economics import normalize_objective
from runtime.tenancy import as_tenant_id


def build_autopilot_request(*, payload: dict[str, Any], route: Any) -> AdsAutopilotRequest:
    p = payload or {}
    tenant_id = as_tenant_id(str(p.get("tenant_id") or ""))
    return AdsAutopilotRequest(
        tenant_id=str(tenant_id),
        objective=normalize_objective(p.get("objective")),
        offer=dict(p.get("offer") or {}),
        audience=dict(p.get("audience") or {}),
        channels=list(p.get("channels") or []),
        constraints=AdsAutopilotConstraints(
            max_daily_budget_minor=int(p.get("max_daily_budget_minor") or 0),
            currency=str(p.get("currency") or "RUB"),
            max_spend_minor=int(p.get("max_spend_minor") or 0),
            max_cpa_minor=int(p.get("max_cpa_minor") or 0),
            min_roas_x1000=int(p.get("min_roas_x1000") or 0),
            allowed_platforms=list(p.get("allowed_platforms") or []),
        ),
        dry_run=True,
        plan_only=True,
        apply_enabled=False,
        correlation_id=str(getattr(route, "correlation_id", "") or ""),
        decision_id=str(getattr(route, "decision_id", "") or ""),
        issuer_id=str(getattr(route, "issuer_id", "") or ""),
        issued_action=str(getattr(route, "issued_action", "") or ""),
        route=str(getattr(route, "route", "") or ""),
    )
