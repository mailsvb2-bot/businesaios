from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from kernel.world_state import WorldStateV1


@dataclass
class OfferOutcomeEmitPolicyV1:
    """System policy: convert a prepared job into a tracking event.

    Invariants:
    - no side effects here; only produces a single action (track_event@v1)
    - deterministic for the same state.meta.job
    """
    id: str = "offer_outcome_emit" + "@v1"

    def propose(self, state: WorldStateV1):
        meta = getattr(state, "meta", None) or {}
        job: dict[str, Any] = {}
        if isinstance(meta, dict):
            j = meta.get("job")
            if isinstance(j, dict):
                job = dict(j)

        user_id = str(job.get("user_id") or "").strip() or "unknown"
        event_type = "offer_outcome"
        payload = dict(job)

        return type(
            "O",
            (),
            {"action": "track_event@v1", "payload": {"user_id": user_id, "event_type": event_type, "payload": payload}},
        )()
