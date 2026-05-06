"""Re-export of settings models for backward compatibility.

Canonical config loading: runtime.platform.config.registry.CONFIG.settings().
Do not add new config paths here; use CONFIG.
"""
from __future__ import annotations

from config.settings_models import (
    CoreSettings,
    DatabaseSettings,
    EvolutionSettings,
    GuardSettings,
    GiftSettings,
    MarketingSettings,
    PaymentsSettings,
    PerfSettings,
    PricingConfig,
    ReadModelSettings,
    Settings,
    TelegramSettings,
)

__all__ = [
    "CoreSettings",
    "DatabaseSettings",
    "EvolutionSettings",
    "GuardSettings",
    "GiftSettings",
    "MarketingSettings",
    "PaymentsSettings",
    "PerfSettings",
    "PricingConfig",
    "ReadModelSettings",
    "Settings",
    "TelegramSettings",
]
