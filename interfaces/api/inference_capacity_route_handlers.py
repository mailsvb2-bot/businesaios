from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from runtime.inference.provisioning.capacity_state_store import InferenceCapacityStateStore


CANON_API_INFERENCE_CAPACITY_ROUTE_HANDLERS = True


@dataclass(frozen=True)
class InferenceCapacityRouteHandlers:
    state_store: InferenceCapacityStateStore = field(default_factory=InferenceCapacityStateStore)

    def get_capacity_state(self) -> dict[str, Any]:
        state = self.state_store.get()
        return {
            'active_tier': state.active_tier.value,
            'frozen': bool(state.frozen),
            'last_transition_ts': float(state.last_transition_ts),
            'read_only': True,
        }

    def freeze_auto_escalation(self, *, frozen: bool) -> dict[str, Any]:
        self.state_store.set_frozen(frozen)
        return {'frozen': bool(frozen), 'read_only': True}
