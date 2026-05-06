from __future__ import annotations

from core.world_model.types import DemandState


class DemandStateBuilder:
    def build(
        self,
        *,
        revenue_payload: dict | None,
        campaign_payload: dict | None,
        market_payload: dict | None,
        messaging_payload: dict | None,
    ) -> DemandState:
        revenue = dict(revenue_payload or {})
        campaign = dict(campaign_payload or {})
        market = dict(market_payload or {})
        messaging = dict(messaging_payload or {})
        revenue_7d = float(revenue.get("revenue_7d") or 0.0)
        orders_7d = int(revenue.get("orders_7d") or 0)
        conversion_rate = revenue.get("conversion_rate")
        campaign_pressure = campaign.get("campaign_pressure")
        if revenue_7d > 0 and orders_7d > 0:
            level = "observed"
        elif campaign.get("active_campaigns"):
            level = "campaign_driven"
        elif market.get("seasonality") not in {None, "", "unknown"}:
            level = "market_inferred"
        elif messaging.get("reply_rate_7d") not in {None, ""}:
            level = "messaging_inferred"
        else:
            level = "unknown"
        confidence = 1.0 if level == "observed" else 0.5 if level != "unknown" else 0.0
        return DemandState(
            level=level,
            confidence=float(confidence),
            revenue_7d=revenue_7d,
            orders_7d=orders_7d,
            conversion_rate=float(conversion_rate) if conversion_rate is not None else None,
            campaign_pressure=float(campaign_pressure) if campaign_pressure is not None else None,
            demand_trend=level,
            signals={"revenue": revenue, "campaign": campaign, "market": market, "messaging": messaging},
        )
