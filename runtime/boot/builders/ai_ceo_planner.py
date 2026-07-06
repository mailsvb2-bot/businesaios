from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from runtime.ai_ceo import (
    AutonomyPolicyV1,
    GrowthSnapshotV1,
    build_intent,
    build_session_args,
    normalize_objective,
    parse_horizon_days,
    read_growth_snapshot,
)
from runtime.ai_ceo import (
    build_plan as build_ai_ceo_plan,
)
from runtime.tenancy import normalize_tenant_id_or_unknown
from runtime.world_state import WorldStateV1

CANON_BOOT_WIRING_ONLY = True

@dataclass(frozen=True)
class RuntimeAICeoPlanner:
    event_store: Any | None = None

    def build_plan(
        self,
        *,
        tenant_id: str,
        objective: str,
        horizon: str,
        decision_id: str,
        correlation_id: str,
    ):
        tenant_scope = normalize_tenant_id_or_unknown(tenant_id)
        normalized_objective = _normalize_objective(objective)
        normalized_horizon_days = _normalize_horizon_days(horizon)
        normalized_decision_id = _normalize_token(decision_id)
        normalized_correlation_id = _normalize_token(correlation_id)

        snapshot = read_growth_snapshot(self.event_store, tenant_id=tenant_scope) if self.event_store is not None else None
        if snapshot is None:
            snapshot = GrowthSnapshotV1()
        state = WorldStateV1(
            schema_version=1,
            tenant_id=tenant_scope,
            user_id="system",
            user={"user_id": "system", "locale": "ru"},
            session={
                "channel": "telegram",
                "locale": "ru",
                "args": _session_args(horizon=normalized_horizon_days),
                "objective": normalized_objective,
            },
            product={},
            economy={},
            timestamp_ms=0,
            meta={
                "decision_id": normalized_decision_id,
                "correlation_id": normalized_correlation_id,
                "source": "runtime.ai_ceo_planner",
            },
        )
        return build_ai_ceo_plan(
            state=state,
            snapshot=snapshot,
            autonomy=AutonomyPolicyV1(),
            intent=build_intent(objective=normalized_objective, horizon=normalized_horizon_days, risk_level="low"),
            plan_id=normalized_decision_id or normalized_correlation_id or "ai_ceo_plan",
        )


def _normalize_token(value: str | None) -> str:
    return str(value or "").strip()


def _normalize_objective(value: str | None) -> str:
    return normalize_objective(value, default="increase_profit")


def _normalize_horizon_days(value: str | None) -> int:
    return parse_horizon_days(value, default=14)


def _session_args(*, horizon: str | int | None) -> str:
    return build_session_args(horizon=horizon, risk_level="low")



def build_runtime_ai_ceo_planner(*, event_store: Any | None):
    return RuntimeAICeoPlanner(event_store=event_store)
