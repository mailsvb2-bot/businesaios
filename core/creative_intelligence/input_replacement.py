from __future__ import annotations

from dataclasses import replace

from core.creative_intelligence.models import CreativeEconomicsInput


def replace_market_fit_score(item: CreativeEconomicsInput, market_fit_score: float) -> CreativeEconomicsInput:
    return replace(item, market_fit_score=market_fit_score)
