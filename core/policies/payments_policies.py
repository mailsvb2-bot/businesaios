from __future__ import annotations

from dataclasses import dataclass

from kernel.world_state import WorldStateV1


@dataclass
class PaymentsReconcilePolicyV1:
    id: str = "payments_reconcile" + "@v1"

    def __init__(self, *, window_min: int = 30):
        self._window_min = int(window_min)

    def propose(self, state: WorldStateV1):
        return type(
            "O",
            (),
            {"action": "reconcile_payments@v1", "payload": {"window_min": int(self._window_min)}},
        )()
