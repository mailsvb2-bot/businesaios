"""Pricing domain.

This package contains small, testable primitives for pricing.

Rules:
- No runtime I/O in core primitives.
- Any event-store access must be explicit via passed ports.
- No "second brain": pricing decisions must be explainable and auditable.
"""

from core.pricing.rl_picker import RLPricingConfig, choose_price_rub
from core.pricing.stop_loss import StopLossConfig, should_apply_price
from core.pricing.autopricing import AutopricingConfig, suggest_prices_for_plans
from core.pricing.market_math import MarketPriceSummary, summarize_market_price

__all__ = ["RLPricingConfig", "choose_price_rub", "StopLossConfig", "should_apply_price", "AutopricingConfig", "suggest_prices_for_plans", "MarketPriceSummary", "summarize_market_price"]
