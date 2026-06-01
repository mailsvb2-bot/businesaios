from __future__ import annotations

from dataclasses import dataclass

from application.headless.models import CEOParticipation, GoalExecutionReport, GoalExecutionRequest
from execution.headless_boot import build_headless_runtime

CANON_HEADLESS_CLIENT = True


@dataclass(frozen=True)
class BusinesAIOSHeadlessClient:
    """
    Thin Python client.

    It does not implement decision logic.
    It delegates to the single headless execution contract.
    """

    def execute(
        self,
        *,
        goal: str,
        business_id: str,
        tenant_id: str = "default",
        user_id: str | None = None,
        region: str = "global",
        max_steps: int = 1,
        profile: dict | None = None,
        signals: list[dict] | None = None,
        constraints: dict | None = None,
        economy: dict | None = None,
        meta: dict | None = None,
        ceo_enabled: bool = False,
        ceo_horizon: str = "30d",
        ceo_risk_level: str = "conservative",
    ) -> GoalExecutionReport:
        runtime = build_headless_runtime(entrypoint="headless_sdk")
        request = GoalExecutionRequest(
            goal=goal,
            business_id=business_id,
            tenant_id=tenant_id,
            user_id=user_id,
            region=region,
            max_steps=max_steps,
            profile=dict(profile or {}),
            signals=list(signals or []),
            constraints=dict(constraints or {}),
            economy=dict(economy or {}),
            meta=dict(meta or {}),
            ceo=CEOParticipation(
                enabled=bool(ceo_enabled),
                objective=goal,
                horizon=ceo_horizon,
                risk_level=ceo_risk_level,
            ),
        )
        return runtime.contract.execute_autopilot(request)


__all__ = ["CANON_HEADLESS_CLIENT", "BusinesAIOSHeadlessClient"]
