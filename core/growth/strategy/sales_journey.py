from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class SalesJourneyState(StrEnum):
    DISCOVERED = "discovered"
    ENGAGED = "engaged"
    NEED_KNOWN = "need_known"
    QUALIFIED = "qualified"
    OFFER_PRESENTED = "offer_presented"
    CHECKOUT = "checkout"
    WON = "won"


class SalesJourneyDisposition(StrEnum):
    OPEN = "open"
    LOST = "lost"
    WON = "won"


class SalesJourneyEvent(StrEnum):
    INBOUND_RECEIVED = "inbound_received"
    CONTACT_RECORDED = "contact_recorded"
    NEED_CAPTURED = "need_captured"
    QUALIFICATION_PASSED = "qualification_passed"
    QUALIFICATION_FAILED = "qualification_failed"
    OFFER_PRESENTED = "offer_presented"
    CHECKOUT_STARTED = "checkout_started"
    PAYMENT_CONFIRMED = "payment_confirmed"
    DECLINED = "declined"
    HUMAN_REQUESTED = "human_requested"
    RISK_ESCALATED = "risk_escalated"
    HUMAN_RESUMED = "human_resumed"


@dataclass(frozen=True, slots=True)
class SalesJourneyProjection:
    state: SalesJourneyState = SalesJourneyState.DISCOVERED
    disposition: SalesJourneyDisposition = SalesJourneyDisposition.OPEN


@dataclass(frozen=True, slots=True)
class SalesJourneyTransition:
    previous: SalesJourneyProjection
    event: SalesJourneyEvent
    current: SalesJourneyProjection

    def as_event_payload(self) -> dict[str, str]:
        return {
            "from": self.previous.state.value,
            "from_disposition": self.previous.disposition.value,
            "event": self.event.value,
            "to": self.current.state.value,
            "to_disposition": self.current.disposition.value,
        }


_PROGRESS_RANK = {
    SalesJourneyState.DISCOVERED: 0,
    SalesJourneyState.ENGAGED: 1,
    SalesJourneyState.NEED_KNOWN: 2,
    SalesJourneyState.QUALIFIED: 3,
    SalesJourneyState.OFFER_PRESENTED: 4,
    SalesJourneyState.CHECKOUT: 5,
    SalesJourneyState.WON: 6,
}

_TARGET_BY_EVENT = {
    SalesJourneyEvent.INBOUND_RECEIVED: SalesJourneyState.ENGAGED,
    SalesJourneyEvent.CONTACT_RECORDED: SalesJourneyState.ENGAGED,
    SalesJourneyEvent.NEED_CAPTURED: SalesJourneyState.NEED_KNOWN,
    SalesJourneyEvent.QUALIFICATION_PASSED: SalesJourneyState.QUALIFIED,
    SalesJourneyEvent.OFFER_PRESENTED: SalesJourneyState.OFFER_PRESENTED,
    SalesJourneyEvent.CHECKOUT_STARTED: SalesJourneyState.CHECKOUT,
}

_HANDOFF_EVENTS = frozenset(
    {
        SalesJourneyEvent.HUMAN_REQUESTED,
        SalesJourneyEvent.RISK_ESCALATED,
        SalesJourneyEvent.HUMAN_RESUMED,
    }
)


def sales_journey_rank(state: SalesJourneyState | str) -> int:
    normalized = state if isinstance(state, SalesJourneyState) else SalesJourneyState(str(state))
    return _PROGRESS_RANK[normalized]


def _projection(value: SalesJourneyProjection | SalesJourneyState | str) -> SalesJourneyProjection:
    if isinstance(value, SalesJourneyProjection):
        return value
    state = value if isinstance(value, SalesJourneyState) else SalesJourneyState(str(value))
    disposition = (
        SalesJourneyDisposition.WON
        if state == SalesJourneyState.WON
        else SalesJourneyDisposition.OPEN
    )
    return SalesJourneyProjection(state=state, disposition=disposition)


def reduce_sales_journey(
    projection: SalesJourneyProjection | SalesJourneyState | str,
    event: SalesJourneyEvent | str,
) -> SalesJourneyTransition:
    """Project hard sales evidence without choosing a business action.

    Funnel progress and disposition are separate facts. This preserves milestones
    after a decline, lets newer positive evidence reopen a lead, and keeps handoff
    orthogonal to sales-stage truth. A confirmed payment is the strongest terminal
    evidence and cannot be downgraded by later events.
    """

    current = _projection(projection)
    signal = event if isinstance(event, SalesJourneyEvent) else SalesJourneyEvent(str(event))

    if signal in _HANDOFF_EVENTS:
        return SalesJourneyTransition(current, signal, current)
    if signal == SalesJourneyEvent.PAYMENT_CONFIRMED:
        won = SalesJourneyProjection(
            state=SalesJourneyState.WON,
            disposition=SalesJourneyDisposition.WON,
        )
        return SalesJourneyTransition(current, signal, won)
    if current.disposition == SalesJourneyDisposition.WON:
        return SalesJourneyTransition(current, signal, current)
    if signal in {SalesJourneyEvent.DECLINED, SalesJourneyEvent.QUALIFICATION_FAILED}:
        lost = SalesJourneyProjection(
            state=current.state,
            disposition=SalesJourneyDisposition.LOST,
        )
        return SalesJourneyTransition(current, signal, lost)

    target = _TARGET_BY_EVENT.get(signal)
    if target is None:
        raise ValueError(f"sales_journey_event_not_supported:{signal.value}")
    next_state = (
        current.state
        if sales_journey_rank(current.state) >= sales_journey_rank(target)
        else target
    )
    reopened = SalesJourneyProjection(
        state=next_state,
        disposition=SalesJourneyDisposition.OPEN,
    )
    return SalesJourneyTransition(current, signal, reopened)


def replay_sales_journey(
    events: list[SalesJourneyEvent | str] | tuple[SalesJourneyEvent | str, ...],
    *,
    initial: SalesJourneyProjection | SalesJourneyState = SalesJourneyState.DISCOVERED,
) -> SalesJourneyProjection:
    projection = _projection(initial)
    for event in events:
        projection = reduce_sales_journey(projection, event).current
    return projection


__all__ = [
    "SalesJourneyDisposition",
    "SalesJourneyEvent",
    "SalesJourneyProjection",
    "SalesJourneyState",
    "SalesJourneyTransition",
    "reduce_sales_journey",
    "replay_sales_journey",
    "sales_journey_rank",
]
