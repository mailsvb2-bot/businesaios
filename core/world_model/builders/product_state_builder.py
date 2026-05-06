from __future__ import annotations

from core.world_model.types import ProductState


class ProductStateBuilder:
    def build(self, payload: dict | None) -> ProductState:
        data = dict(payload or {})
        price = data.get("price")
        margin = data.get("margin")
        return ProductState(
            product_id=str(data.get("product_id") or "unknown"),
            title=str(data.get("title") or "unknown"),
            price=float(price) if price is not None else None,
            margin=float(margin) if margin is not None else None,
            inventory_status=str(data.get("inventory_status") or "unknown"),
            attributes=dict(data.get("attributes") or {}),
        )
