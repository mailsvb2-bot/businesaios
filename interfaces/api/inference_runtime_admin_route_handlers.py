from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from core.tenancy.normalization import require_tenant_id
from observability.inference_runtime_summary import InferenceRuntimeSummaryService
from runtime.inference.provisioning.capacity_state_store import InferenceCapacityStateStore

CANON_API_INFERENCE_RUNTIME_ADMIN_ROUTE_HANDLERS = True


@dataclass(frozen=True)
class InferenceRuntimeAdminRouteHandlers:
    summary_service: InferenceRuntimeSummaryService
    state_store: InferenceCapacityStateStore | None = None

    def get_runtime_admin_payload(self, *, tenant_id: str | None = None) -> dict[str, Any]:
        required_tenant_id = require_tenant_id(tenant_id) if tenant_id is not None else None
        payload = self.summary_service.build(tenant_id=required_tenant_id)
        return {
            'tenant_id': required_tenant_id,
            'active_tier': payload['active_tier'],
            'frozen': payload['frozen'],
            'providers': payload['providers'],
            'provider_mix': payload['provider_mix'],
            'tier_mix': payload['tier_mix'],
            'verification_summary': payload['verification_summary'],
            'recent_escalations': payload['recent_escalations'],
            'headroom_usd': payload['headroom_usd'],
            'burn_rate_usd_per_hour': payload['burn_rate_usd_per_hour'],
            'total_estimated_cost_usd': payload['total_estimated_cost_usd'],
            'selection_count': payload['selection_count'],
            'escalation_event_count': payload['escalation_event_count'],
            'acceleration_summary': payload['acceleration_summary'],
            'read_only': True,
        }

    def apply_manual_freeze(self, *, tenant_id: str, frozen: bool) -> dict[str, Any]:
        required_tenant_id = require_tenant_id(tenant_id)
        if self.state_store is None:
            raise RuntimeError('Inference runtime admin route handlers require a state store for mutating operations.')
        self.state_store.set_frozen(frozen)
        state = self.state_store.get()
        return {
            'tenant_id': required_tenant_id,
            'frozen': bool(state.frozen),
            'active_tier': state.active_tier.value,
            'last_transition_ts': float(state.last_transition_ts),
            'read_only': False,
        }


__all__ = ['CANON_API_INFERENCE_RUNTIME_ADMIN_ROUTE_HANDLERS', 'InferenceRuntimeAdminRouteHandlers']
