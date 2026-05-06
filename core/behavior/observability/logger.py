from __future__ import annotations

from typing import Protocol

from core.behavior.observability.structured_events import build_behavior_structured_event


class EventWriter(Protocol):
    def write(self, event: dict[str, object]) -> None:
        ...


class BehaviorLogger:
    def __init__(self, writer: EventWriter) -> None:
        self._writer = writer

    def log_policy_denials(self, entity_id: str, policy_denials: dict[str, int]) -> None:
        self._writer.write(
            build_behavior_structured_event(
                "policy_denials",
                {
                    "entity_id": entity_id,
                    "policy_denials": dict(policy_denials),
                },
            )
        )

    def log_market_snapshot(self, market_id: str, observables: dict[str, float]) -> None:
        self._writer.write(
            build_behavior_structured_event(
                "market_snapshot",
                {
                    "market_id": market_id,
                    "observables": dict(observables),
                },
            )
        )
