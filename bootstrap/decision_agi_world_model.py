from __future__ import annotations

CANON_BOOT_WIRING_ONLY = True

from dataclasses import replace
from typing import Any
from collections.abc import Mapping as AbcMapping

from core.world_model.service import WorldModelService
from core.world_model.types import WorldModelBuildInput, WorldModelBuildResult, WorldSnapshot
from execution.agi_reasoning_engine import AGIReasoningEngine
from bootstrap.canonical_decision_world_model import CanonicalDecisionWorldModel


CANON_DECISION_AGI_WORLD_MODEL = True
DECISION_AGI_WORLD_MODEL_NAME = "decision_agi_world_model@v1"
DECISION_AGI_WORLD_MODEL_KIND = "decision_agi@v1"
DEFAULT_BASE_WORLD_MODEL_KIND = "hybrid@v1"


def _safe_dict(value: object) -> dict[str, Any]:
    if isinstance(value, AbcMapping):
        return dict(value)
    return {}


def _safe_int(value: object, *, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return int(default)


def _text(value: object) -> str:
    return str(value or "").strip()


def _snapshot_to_dict(snapshot: WorldSnapshot | None) -> dict[str, Any]:
    if snapshot is None:
        return {}
    payload = {
        "snapshot_id": snapshot.snapshot_id,
        "tenant_id": snapshot.tenant_id,
        "business_id": snapshot.business_id,
        "confidence": snapshot.confidence,
        "status": str(snapshot.status.value if hasattr(snapshot.status, "value") else snapshot.status),
        "schema_version": snapshot.schema_version,
        "built_at_ms": snapshot.built_at_ms,
        "metadata": dict(snapshot.metadata or {}),
        "explain": dict(snapshot.explain or {}),
    }
    if snapshot.business_state is not None:
        payload["business_state"] = {
            "tenant_id": snapshot.business_state.tenant_id,
            "business_id": snapshot.business_state.business_id,
            "demand_level": snapshot.business_state.demand.level,
            "demand_confidence": snapshot.business_state.demand.confidence,
            "revenue_7d": snapshot.business_state.demand.revenue_7d,
            "orders_7d": snapshot.business_state.demand.orders_7d,
            "competition_index": snapshot.business_state.market.competition_index,
            "channel": snapshot.business_state.market.channel,
            "geo": snapshot.business_state.market.geo,
        }
    return payload


class DecisionAGIWorldModel(CanonicalDecisionWorldModel):
    def __init__(
        self,
        *,
        store=None,
        kind: str = DECISION_AGI_WORLD_MODEL_KIND,
        base_kind: str = DEFAULT_BASE_WORLD_MODEL_KIND,
        world_model_service: WorldModelService | None = None,
        reasoning_engine: AGIReasoningEngine | None = None,
    ) -> None:
        self._agi_kind = str(kind or DECISION_AGI_WORLD_MODEL_KIND).strip().lower() or DECISION_AGI_WORLD_MODEL_KIND
        self._base_kind = str(base_kind or DEFAULT_BASE_WORLD_MODEL_KIND).strip().lower() or DEFAULT_BASE_WORLD_MODEL_KIND
        super().__init__(store=store, kind=self._base_kind)
        self._world_model_service = world_model_service or WorldModelService()
        self._reasoning_engine = reasoning_engine or AGIReasoningEngine()

    def enrich_state(self, state: Any) -> Any:
        enriched = super().enrich_state(state)

        meta = _safe_dict(getattr(enriched, "meta", None))
        economy = _safe_dict(getattr(enriched, "economy", None))
        product = _safe_dict(getattr(enriched, "product", None))
        if not hasattr(enriched, "__dataclass_fields__"):
            return enriched

        user = _safe_dict(getattr(enriched, "user", None))
        session = _safe_dict(getattr(enriched, "session", None))

        snapshot = self._try_build_snapshot(
            tenant_id=_text(getattr(enriched, "tenant_id", "") or meta.get("tenant_id")),
            business_id=_text(meta.get("business_id") or product.get("business_id") or product.get("product_id")),
            customer_id=_text(user.get("customer_id") or user.get("user_id") or getattr(enriched, "user_id", None)),
            product_id=_text(product.get("product_id") or meta.get("product_id")),
            channel=_text(session.get("channel") or product.get("channel") or "unknown"),
            geo=_text(session.get("geo") or product.get("geo") or "unknown"),
            now_ms=_safe_int(getattr(enriched, "timestamp_ms", 0), default=0),
            correlation_id=_text(meta.get("correlation_id") or meta.get("correlation") or meta.get("correlation_key")),
            context={"state_schema_version": getattr(enriched, "schema_version", 1)},
        )
        snapshot_dict = _snapshot_to_dict(snapshot)

        try:
            summary = self._reasoning_engine.build_summary(
                state=enriched,
                world_snapshot=snapshot_dict,
            ).to_dict()
            reasoning_status = "ok"
        except Exception as exc:
            summary = {
                "schema_version": None,
                "reasoning_mode": "state_enrichment_only",
                "selected_goal": None,
                "goal_candidates": [],
                "strategy_hints": [],
                "planning_horizon": "",
                "decomposed_focus": [],
                "world_snapshot": dict(snapshot_dict),
                "opportunity_signals": [],
                "learning_context": {},
                "explainability": {
                    "reasoning_mode": "state_enrichment_only",
                    "selected_goal_present": False,
                    "selected_goal_is_enrichment_only": True,
                    "no_second_brain": True,
                    "decision_owner": "core.ai.decision_core.DecisionCore",
                    "contract_owner": "runtime.boot.world_model_contract.DecisionWorldModelPort",
                    "reasoning_failed_closed": True,
                },
                "suppressed_reasons": [f"reasoning_failed_closed:{exc.__class__.__name__}"],
            }
            reasoning_status = "failed_closed"

        meta["world_model"] = DECISION_AGI_WORLD_MODEL_NAME
        meta["world_model_kind"] = self._agi_kind
        meta["decision_agi_base_world_model_kind"] = self._base_kind
        meta["decision_agi"] = summary
        meta["decision_agi_reasoning_status"] = reasoning_status
        meta["decision_agi_summary"] = {
            "schema_version": summary.get("schema_version"),
            "reasoning_mode": summary.get("reasoning_mode"),
            "selected_goal": _safe_dict(summary.get("selected_goal")).get("goal"),
            "selected_goal_family": _safe_dict(summary.get("selected_goal")).get("goal_family"),
            "planning_horizon": summary.get("planning_horizon"),
            "decomposed_focus": list(summary.get("decomposed_focus") or []),
            "strategy_hints": list(summary.get("strategy_hints") or []),
            "signal_count": len(list(summary.get("opportunity_signals") or [])),
            "suppressed_reasons": list(summary.get("suppressed_reasons") or []),
            "reasoning_status": reasoning_status,
            "no_second_brain": True,
        }
        meta["strategy_hints"] = list(summary.get("strategy_hints") or [])

        if snapshot_dict:
            meta["world_snapshot"] = snapshot_dict
            economy["decision_world_snapshot_confidence"] = snapshot_dict.get("confidence")
            economy["decision_world_snapshot_status"] = snapshot_dict.get("status")
        else:
            meta["decision_agi_world_snapshot_status"] = "unavailable"

        return replace(enriched, meta=meta, economy=economy)

    def _try_build_snapshot(
        self,
        *,
        tenant_id: str,
        business_id: str,
        customer_id: str,
        product_id: str,
        channel: str,
        geo: str,
        now_ms: int,
        correlation_id: str,
        context: dict[str, Any] | None = None,
    ) -> WorldSnapshot | None:
        if not tenant_id or not business_id or not customer_id or not product_id or now_ms <= 0:
            return None
        result = self._build_snapshot_result(
            WorldModelBuildInput(
                tenant_id=tenant_id,
                business_id=business_id,
                customer_id=customer_id,
                product_id=product_id,
                channel=channel or "unknown",
                geo=geo or "unknown",
                now_ms=int(now_ms),
                correlation_id=correlation_id,
                context=dict(context or {}),
            )
        )
        if not result.accepted or result.snapshot is None:
            return None
        return result.snapshot

    def _build_snapshot_result(self, build_input: WorldModelBuildInput) -> WorldModelBuildResult:
        try:
            return self._world_model_service.build_snapshot(build_input=build_input)
        except Exception:
            return WorldModelBuildResult(accepted=False, snapshot=None, rejection=None)


__all__ = [
    "CANON_DECISION_AGI_WORLD_MODEL",
    "DECISION_AGI_WORLD_MODEL_NAME",
    "DECISION_AGI_WORLD_MODEL_KIND",
    "DEFAULT_BASE_WORLD_MODEL_KIND",
    "DecisionAGIWorldModel",
]
