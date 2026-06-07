from __future__ import annotations

from typing import Any

from core.ads.ads_service import AdsPlan, AdsService
from core.ads.autopilot.campaign_builder import AdsAutopilotCampaignBuilder
from core.ads.autopilot.contract import AdsAutopilotRequest, AdsAutopilotResponse
from core.ads.autopilot.stop_loss_guard import StopLossGuard

Json = dict[str, Any]


class AdsAutopilotEngine:
    """Execution helper for one ads-autopilot tick.

    Important invariants:
      - does NOT issue decisions
      - does NOT authorize apply on its own
      - does NOT apply ads changes directly
      - may only build deterministic plans for later guarded execution
    """

    def __init__(self, *, ads: AdsService, builder: AdsAutopilotCampaignBuilder) -> None:
        self._ads = ads
        self._builder = builder


    def _ensure_read_only_ads_surface(self) -> None:
        if callable(getattr(self._ads, 'apply', None)) or callable(getattr(self._ads, 'apply_changes', None)):
            raise ValueError(
                'AdsAutopilotEngine must not be wired with direct apply surface. '
                'Plan execution belongs to ads_apply_execute.'
            )

    def tick(self, req: AdsAutopilotRequest) -> AdsAutopilotResponse:
        req.validate()
        req.validate_executor_route()
        if req.allow_apply():
            if callable(getattr(self._ads, "apply_plan", None)):
                req = AdsAutopilotRequest(
                    tenant_id=req.tenant_id,
                    objective=req.objective,
                    offer=dict(req.offer or {}),
                    audience=dict(req.audience or {}),
                    channels=list(req.channels or ()),
                    constraints=req.constraints,
                    dry_run=True,
                    plan_only=True,
                    apply_enabled=False,
                    decision_id=req.decision_id,
                    correlation_id=req.correlation_id,
                    issuer_id=req.issuer_id,
                    issued_action=req.issued_action,
                    route=req.route,
                )
            else:
                raise ValueError(
                    "AdsAutopilotEngine forbids direct apply. Route plan through ads_apply_execute."
                )
        self._ensure_read_only_ads_surface()

        try:
            metrics = self._ads.metrics(
                req.tenant_id,
                {"scope": "today", "objective": req.objective},
            )
        except Exception as exc:
            return AdsAutopilotResponse(
                status="blocked",
                stop_loss={
                    "allowed": False,
                    "reason": "metrics_unavailable",
                    "snapshot": {"error": exc.__class__.__name__},
                },
                plan={},
                applied={"status": "skipped", "reason": "metrics_unavailable"},
                notes="metrics_unavailable",
            )

        sl = StopLossGuard(
            max_spend_minor=req.constraints.max_spend_minor,
            max_cpa_minor=req.constraints.max_cpa_minor,
            min_roas_x1000=req.constraints.min_roas_x1000,
        ).evaluate(_coerce_json(metrics))

        if not sl.allowed:
            return AdsAutopilotResponse(
                status="blocked",
                stop_loss={
                    "allowed": sl.allowed,
                    "reason": sl.reason,
                    "snapshot": sl.snapshot,
                },
                plan={},
                applied={"status": "skipped", "reason": "stop_loss"},
                notes="stop_loss",
            )

        built = self._builder.build(
            objective=req.objective,
            offer=req.offer,
            audience=req.audience,
            channels=req.channels,
        )

        spec = dict(built.spec or {})
        if req.constraints.allowed_platforms:
            spec["allowed_platforms"] = list(req.constraints.allowed_platforms)

        plan = self._ads.build_plan(req.tenant_id, spec)
        plan_json = _plan_to_json(plan)

        return AdsAutopilotResponse(
            status="ok",
            stop_loss={
                "allowed": sl.allowed,
                "reason": sl.reason,
                "snapshot": sl.snapshot,
            },
            plan=plan_json,
            applied={
                "status": "skipped",
                "reason": "direct_apply_forbidden_use_ads_apply_execute",
                "apply_enabled": False,
                "dry_run": True,
                "plan_only": True,
            },
            notes=built.notes,
        )


def _plan_to_json(plan: AdsPlan) -> Json:
    cmds = []
    for c in plan.commands:
        cmds.append(
            {
                "platform": c.platform,
                "action": c.action,
                "payload": dict(c.payload or {}),
            }
        )
    return {"commands": cmds, "notes": str(plan.notes or "")}


def _coerce_json(x: Any) -> Json:
    if isinstance(x, dict):
        return dict(x)
    return {"value": x}
