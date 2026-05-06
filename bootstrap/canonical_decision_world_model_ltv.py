from __future__ import annotations

CANON_BOOT_WIRING_ONLY = True
CANON_BOOT_CLUSTER_FINAL_OWNER = True

from dataclasses import dataclass

from runtime.boot import UserState, build_ltv_world_model


@dataclass(frozen=True)
class LtvInput:
    user_id: str
    sessions: int
    payments: float
    last_seen: float
    now_s: float | None


class CanonicalLtvEnricher:
    def __init__(self) -> None:
        self._world_model = build_ltv_world_model()

    def predicted_ltv(self, payload: LtvInput) -> float:
        state = self._world_model.build(
            UserState(
                user_id=payload.user_id,
                sessions=payload.sessions,
                payments=payload.payments,
                last_seen=payload.last_seen,
            ),
            now=payload.now_s,
        )
        return float(state.predicted_ltv)
