from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class PriceConstraints:
    max_band: str = "standard"
    mode: str = "normal"
    premium_allowed: bool = True


@dataclass(frozen=True)
class OfferConstraints:
    aggressive_allowed: bool = True
    paywall_first_allowed: bool = True
    disallow_offer_prefixes: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class ContactConstraints:
    retry_cooldown_level: int = 0
    contact_frequency_cap: int = 0


@dataclass(frozen=True)
class SafetyConstraints:
    safe_mode_recommended: bool = False
    guardrails_violation: bool = False
