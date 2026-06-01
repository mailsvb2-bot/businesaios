from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from runtime.inference.provisioning.capacity_state_store import InferenceCapacityStateStore

CANON_API_INFERENCE_ADMIN_ROUTE_HANDLERS = True


@dataclass(frozen=True)
class InferenceAdminRouteHandlers:
    state_store: InferenceCapacityStateStore = field(default_factory=InferenceCapacityStateStore)

    def freeze(self) -> dict[str, Any]:
        self.state_store.set_frozen(True)
        state = self.state_store.get()
        return {
            'ok': True,
            'frozen': True,
            'active_tier': state.active_tier.value,
            'read_only': False,
        }

    def unfreeze(self) -> dict[str, Any]:
        self.state_store.set_frozen(False)
        state = self.state_store.get()
        return {
            'ok': True,
            'frozen': False,
            'active_tier': state.active_tier.value,
            'read_only': False,
        }
