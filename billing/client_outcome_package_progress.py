from __future__ import annotations

from dataclasses import dataclass

from lead_outcomes.client_outcome_contract import ClientOutcomeOrder

CANON_CLIENT_OUTCOME_PACKAGE_PROGRESS = True


@dataclass(frozen=True, slots=True)
class ClientOutcomePackageProgress:
    order_id: str
    requested_clients: int
    verified_clients: int
    billable_clients: int
    remaining_clients: int
    completion_ratio: float
    closed: bool


class ClientOutcomePackageProgressCalculator:
    def calculate(self, *, order: ClientOutcomeOrder, verified_clients: int, billable_clients: int) -> ClientOutcomePackageProgress:
        requested = max(1, int(order.package.requested_clients))
        verified = max(0, int(verified_clients))
        billable = max(0, int(billable_clients))
        remaining = max(0, requested - billable)
        ratio = min(1.0, round(billable / requested, 4))
        return ClientOutcomePackageProgress(order_id=order.order_id, requested_clients=requested, verified_clients=verified, billable_clients=billable, remaining_clients=remaining, completion_ratio=ratio, closed=billable >= requested)
