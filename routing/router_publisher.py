from __future__ import annotations

from routing.router_preparation_validator import RouterPreparationValidator


class RouterPublisher:
    def __init__(self) -> None:
        self._validator = RouterPreparationValidator()

    def publish(self, routing_preparation: dict[str, object]) -> dict[str, object]:
        # Canonical rule: routing prepares candidates only; it never emits a final decision.
        return self._validator.validate(routing_preparation)
