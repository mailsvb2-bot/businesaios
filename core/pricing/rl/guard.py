from __future__ import annotations

from dataclasses import dataclass


class PricingRouteViolation(ValueError):
    pass


@dataclass(frozen=True)
class PricingSelectionContext:
    tenant_id: str
    decision_id: str
    correlation_id: str
    issuer_id: str
    action: str

    def validate(self) -> None:
        if not self.tenant_id:
            raise PricingRouteViolation("tenant_id is required")
        if not self.decision_id:
            raise PricingRouteViolation("decision_id is required")
        if not self.correlation_id:
            raise PricingRouteViolation("correlation_id is required")
        if self.issuer_id != "businesaios-core":
            raise PricingRouteViolation("issuer_id must be 'businesaios-core'")
        if self.action != "pricing_select@v1":
            raise PricingRouteViolation("action must be 'pricing_select@v1'")
