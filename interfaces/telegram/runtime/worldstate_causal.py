from __future__ import annotations

import logging
from dataclasses import replace
from typing import Any, Dict, List

from core.causal.evidence.from_events import (
    build_daily_panel,
    estimate_effect_from_daily_panel,
    placebo_shift_treatment,
)
from kernel.world_state import WorldStateV1

logger = logging.getLogger(__name__)


def build_causal_evidence_from_event_window(events: List[Dict[str, Any]]) -> Dict[str, Any]:
    evs = list(events or [])
    if not evs:
        return {}
    out: Dict[str, Any] = {"schema_version": 1}
    pricing_panel = build_daily_panel(
        evs,
        treatment_event_types=("pricing_change_applied",),
        outcome_event_types=("payment_captured", "payment_succeeded", "grant_access"),
        max_days=60,
    )
    pricing_effect = estimate_effect_from_daily_panel(pricing_panel, method="dr")
    pricing_placebo = placebo_shift_treatment(pricing_panel, shift_days=1, method="dr")
    if pricing_effect is not None:
        out["pricing"] = {
            "method": pricing_effect.method,
            "effect": pricing_effect.effect,
            "ci_low": pricing_effect.ci_low,
            "ci_high": pricing_effect.ci_high,
            "n_days": int(pricing_panel.meta.get("n_days") or 0),
            "y_kind": str(pricing_panel.meta.get("y_kind") or ""),
            "placebo_effect": pricing_placebo.effect if pricing_placebo is not None else None,
            "placebo_ci": [pricing_placebo.ci_low, pricing_placebo.ci_high] if pricing_placebo is not None else None,
        }

    ads_panel = build_daily_panel(
        evs,
        treatment_event_types=("ads_apply_executed@v1", "ads_apply_audit@v1"),
        outcome_event_types=("payment_captured", "payment_succeeded", "grant_access"),
        max_days=60,
    )
    ads_effect = estimate_effect_from_daily_panel(ads_panel, method="dr")
    ads_placebo = placebo_shift_treatment(ads_panel, shift_days=1, method="dr")
    if ads_effect is not None:
        out["ads"] = {
            "method": ads_effect.method,
            "effect": ads_effect.effect,
            "ci_low": ads_effect.ci_low,
            "ci_high": ads_effect.ci_high,
            "n_days": int(ads_panel.meta.get("n_days") or 0),
            "y_kind": str(ads_panel.meta.get("y_kind") or ""),
            "placebo_effect": ads_placebo.effect if ads_placebo is not None else None,
            "placebo_ci": [ads_placebo.ci_low, ads_placebo.ci_high] if ads_placebo is not None else None,
        }
    return out


def apply_causal_overlay(*, ws: WorldStateV1, events: List[Dict[str, Any]]) -> WorldStateV1:
    try:
        causal = build_causal_evidence_from_event_window(events)
        if not isinstance(causal, dict) or not causal:
            return ws
        economy = dict(ws.economy or {})
        economy["causal_evidence"] = dict(causal)
        return replace(ws, economy=economy)
    except Exception as err:
        logger.warning("[worldstate_builder] WorldState causal overlay failed (UX preserved): %r", err)
        return ws
