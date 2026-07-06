from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from core.observability.perf import stable_hash_01
from core.observability.silent import swallow
from core.offers.models import OfferVariant


def choose_offer_variant(*, seed: str, variants: list[OfferVariant]) -> OfferVariant:
    if not variants:
        raise ValueError("NO_VARIANTS")
    if len(variants) == 1:
        return variants[0]
    r = stable_hash_01(seed)
    idx = int(r * len(variants))
    if idx >= len(variants):
        idx = len(variants) - 1
    return variants[idx]


def eligible(*, behavior: Mapping[str, Any], rule) -> bool:
    try:
        eng = float(behavior.get("engagement_score") or 0.0)
        fat = float(behavior.get("fatigue_index") or 0.0)
    except Exception:
        return False
    if eng < float(getattr(rule, "min_engagement", 0.0) or 0.0):
        return False
    return fat <= float(getattr(rule, "max_fatigue", 1.0) or 1.0)


def choose_slot(*, behavior: Mapping[str, Any]) -> str:
    try:
        if int(behavior.get("audio_starts") or 0) > 0 and int(behavior.get("audio_completions") or 0) == 0:
            return "reengage_audio"
        if int(behavior.get("fast_actions_10s") or 0) >= 3:
            return "high_arousal_short"
    except Exception:
        swallow(__name__, 'core/offers/selection_policy.py')
    return "default_menu"


def choose_band(*, behavior: Mapping[str, Any]) -> str:
    try:
        if int(behavior.get("audio_completions") or 0) >= 1:
            return "premium"
        if int(behavior.get("clicks_total") or 0) >= 10:
            return "standard"
    except Exception:
        swallow(__name__, 'core/offers/selection_policy.py')
    return "low"


def clamp_band(band: str, max_band: str | None) -> str:
    order = {"low": 0, "standard": 1, "premium": 2}
    if band not in order:
        band = "standard"
    if not max_band or max_band not in order:
        return band
    return band if order[band] <= order[max_band] else str(max_band)
