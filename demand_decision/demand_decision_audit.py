from __future__ import annotations


class DemandDecisionAudit:
    def __init__(self) -> None:
        self._rows: list[dict[str, object]] = []

    def record(self, *, packet: dict[str, object], decision: object) -> None:
        self._rows.append({
            "request_id": packet["request_id"],
            "customer_id": packet["customer_id"],
            "selected_business_id": decision.selected_business_id,
            "requires_manual_review": decision.requires_manual_review,
        })

    def rows(self) -> tuple[dict[str, object], ...]:
        return tuple(self._rows)
