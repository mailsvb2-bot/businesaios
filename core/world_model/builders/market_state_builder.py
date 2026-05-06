from __future__ import annotations

from core.world_model.types import MarketState


class MarketStateBuilder:
    def build(
        self,
        *,
        market_payload: dict | None,
        campaign_payload: dict | None,
        messaging_payload: dict | None,
        channel: str,
        geo: str,
    ) -> MarketState:
        market = dict(market_payload or {})
        competition_index = market.get("competition_index")
        cpm = market.get("cpm")
        return MarketState(
            channel=str(market.get("channel") or channel or "unknown"),
            geo=str(market.get("geo") or geo or "unknown"),
            competition_index=float(competition_index) if competition_index is not None else None,
            cpm=float(cpm) if cpm is not None else None,
            seasonality=str(market.get("seasonality") or "unknown"),
            signals={
                "market": market,
                "campaign": dict(campaign_payload or {}),
                "messaging": dict(messaging_payload or {}),
            },
        )
