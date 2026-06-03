from __future__ import annotations

"""Campaign builder (canonical, deterministic).

Goal: produce a *plan* for AdsWriteGateway without side-effects.

Rules:
- No network, no time-based randomness.
- Output is a plain dict that can be:
  - previewed in UI
  - hashed for idempotency
  - executed only via runtime sealed handler.
"""

from dataclasses import dataclass
from typing import Any
from collections.abc import Mapping


@dataclass(frozen=True)
class CampaignSpec:
    tenant_id: str
    platform: str  # meta|yandex_direct|vk|telegram_ads
    offer_id: str
    offer_title: str
    daily_budget_minor: int
    region: str = ""
    what: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "tenant_id": self.tenant_id,
            "platform": self.platform,
            "offer_id": self.offer_id,
            "offer_title": self.offer_title,
            "daily_budget_minor": int(self.daily_budget_minor),
            "region": self.region,
            "what": self.what,
        }


def build_ads_write_plan(*, spec: CampaignSpec) -> dict[str, Any]:
    """Return AdsWriteGateway plan payload.

    Contract:
      {"ops": [{"account_id": "...", "object_type": "campaign", "payload": {...}}, ...]}

    NOTE: account_id is resolved by connector/vault; here we keep it blank and let
    runtime fill it from settings (safe, explicit).
    """

    name = f"BAIOS:{spec.offer_title[:20]}"
    return {
        "platform": str(spec.platform),
        "daily_budget_minor": int(spec.daily_budget_minor),
        "ops": [
            {
                "account_id": "",  # must be resolved at runtime
                "object_type": "campaign",
                "payload": {
                    "name": name,
                    "offer_id": str(spec.offer_id),
                    "region": str(spec.region or ""),
                    "what": str(spec.what or ""),
                    "daily_budget_minor": int(spec.daily_budget_minor),
                },
            }
        ],
    }


def plan_from_onboarding(
    *,
    tenant_id: str,
    platform: str,
    offer_id: str,
    offer_title: str,
    diag: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Build a minimal plan from onboarding diagnostics."""

    d = dict(diag or {})
    budget_minor_7d = int((d.get("budget_minor_7d") or 0) or 0)
    # Default: 7d budget / 7
    daily = max(0, int(budget_minor_7d // 7)) if budget_minor_7d > 0 else 0
    # Conservative fallback if unknown: 0 (guardrails decide)
    spec = CampaignSpec(
        tenant_id=str(tenant_id),
        platform=str(platform),
        offer_id=str(offer_id),
        offer_title=str(offer_title or "Offer"),
        daily_budget_minor=int(daily),
        region=str(d.get("region") or ""),
        what=str(d.get("what") or ""),
    )
    return build_ads_write_plan(spec=spec)
