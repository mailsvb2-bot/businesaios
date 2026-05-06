from __future__ import annotations

CANON_DEMAND_PRODUCT_ALIAS_NAMESPACE = True
CANON_DEMAND_PRODUCT_PACKAGE_OWNER = True

class BusinessValueSummary:
    def summarize(self, revenue: float, leads: int, conversions: int) -> dict[str, float]:
        return {"revenue": float(revenue), "lead_to_conversion": conversions / max(1, leads)}

class CustomerSuccessNotifications:
    def notify(self, request_id: str, event_code: str) -> dict[str, object]:
        return {"request_id": request_id, "event_code": event_code}

class FirstConversionDetector:
    def detect(self, state: dict[str, object]) -> bool:
        return not bool(state.get("first_conversion_seen")) and bool(state.get("converted"))

class FirstLeadDeliveredDetector:
    def detect(self, state: dict[str, object]) -> bool:
        return not bool(state.get("first_lead_delivered_seen")) and bool(state.get("delivered"))

class FirstMatchDetector:
    def detect(self, state: dict[str, object]) -> bool:
        return not bool(state.get("first_match_seen")) and bool(state.get("matched"))

class FirstRevenueDetector:
    def detect(self, state: dict[str, object]) -> bool:
        return not bool(state.get("first_revenue_seen")) and float(state.get("revenue") or 0.0) > 0.0

class MagicMomentPublisher:
    def publish(self, code: str, business_id: str) -> dict[str, object]:
        return {"code": str(code), "business_id": str(business_id)}

__all__ = [
    "CANON_DEMAND_PRODUCT_ALIAS_NAMESPACE",
    "CANON_DEMAND_PRODUCT_PACKAGE_OWNER",
    "BusinessValueSummary",
    "CustomerSuccessNotifications",
    "FirstConversionDetector",
    "FirstLeadDeliveredDetector",
    "FirstMatchDetector",
    "FirstRevenueDetector",
    "MagicMomentPublisher",
]
