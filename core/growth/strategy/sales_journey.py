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
    LOST = "lost"


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
class SalesJourneyTransition:
    previous: SalesJourneyState
    event: SalesJourneyEvent
    current: SalesJourneyState

    def as_event_payload(self) -> dict[str, str]:
        return {
            "from": self.previous.value,
            "event": self.event.value,
            "to": self.current.value,
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
    return _PROGRESS_RANK.get(normalized, -1)


def reduce_sales_journey(
    state: SalesJourneyState | str,
    event: SalesJourneyEvent | str,
) -> SalesJourneyTransition:
    """Project hard sales evidence without choosing a business action.

    The reducer is deliberately replay-safe. Handoff is orthogonal evidence and
    therefore never becomes a competing funnel state. ``won`` is the strongest
    terminal fact. ``lost`` may be reopened by newer positive evidence because a
    declined lead can legitimately re-engage later.
    """

    current = state if isinstance(state, SalesJourneyState) else SalesJourneyState(str(state))
    signal = event if isinstance(event, SalesJourneyEvent) else SalesJourneyEvent(str(event))

    if signal in _HANDOFF_EVENTS:
        return SalesJourneyTransition(current, signal, current)
    if signal == SalesJourneyEvent.PAYMENT_CONFIRMED:
        return SalesJourneyTransition(current, signal, SalesJourneyState.WON)
    if current == SalesJourneyState.WON:
        return SalesJourneyTransition(current, signal, current)
    if signal in {SalesJourneyEvent.DECLINED, SalesJourneyEvent.QUALIFICATION_FAILED}:
        return SalesJourneyTransition(current, signal, SalesJourneyState.LOST)

    target = _TARGET_BY_EVENT.get(signal)
    if target is None:
        raise ValueError(f"sales_journey_event_not_supported:{signal.value}")
    if current == SalesJourneyState.LOST:
        return SalesJourneyTransition(current, signal, target)
    if sales_journey_rank(current) >= sales_journey_rank(target):
        return SalesJourneyTransition(current, signal, current)
    return SalesJourneyTransition(current, signal, target)


def replay_sales_journey(
    events: list[SalesJourneyEvent | str] | tuple[SalesJourneyEvent | str, ...],
    *,
    initial: SalesJourneyState = SalesJourneyState.DISCOVERED,
) -> SalesJourneyState:
    state = initial
    for event in events:
        state = reduce_sales_journey(state, event).current
    return state


__all__ = [
    "SalesJourneyEvent",
    "SalesJourneyState",
    "SalesJourneyTransition",
    "reduce_sales_journey",
    "replay_sales_journey",
    "sales_journey_rank",
]
