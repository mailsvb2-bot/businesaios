from __future__ import annotations

from core.world_model.types import BusinessState, CustomerState, DemandState, MarketState, ProductState


class BusinessStateBuilder:
    def build(
        self,
        *,
        tenant_id: str,
        business_id: str,
        customer: CustomerState,
        product: ProductState,
        demand: DemandState,
        market: MarketState,
        messaging_payload: dict | None,
        revenue_payload: dict | None,
    ) -> BusinessState:
        revenue = dict(revenue_payload or {})
        return BusinessState(
            tenant_id=str(tenant_id),
            business_id=str(business_id),
            customer=customer,
            product=product,
            demand=demand,
            market=market,
            messaging=dict(messaging_payload or {}),
            economics={
                "revenue_7d": float(revenue.get("revenue_7d") or 0.0),
                "orders_7d": int(revenue.get("orders_7d") or 0),
            },
        )
