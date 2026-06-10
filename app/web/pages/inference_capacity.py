from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

from app.web.components.inference_queue_pressure_panel import InferenceQueuePressurePanel
from app.web.components.inference_tier_panel import InferenceTierPanel
from app.web.components.provider_health_panel import InferenceProviderHealthPanel
from core.tenancy.normalization import require_tenant_id

CANON_WEB_INFERENCE_CAPACITY_PAGE = True


@dataclass(frozen=True, slots=True)
class InferenceCapacityPage:
    tier_panel: InferenceTierPanel = field(default_factory=InferenceTierPanel)
    queue_pressure_panel: InferenceQueuePressurePanel = field(default_factory=InferenceQueuePressurePanel)
    provider_health_panel: InferenceProviderHealthPanel = field(default_factory=InferenceProviderHealthPanel)

    def build(self, payload: Mapping[str, Any] | None) -> dict[str, Any]:
        normalized = dict(payload or {})
        tenant_id = require_tenant_id(normalized.get('tenant_id'))
        return {
            'tenant_id': tenant_id,
            'title': 'Inference Capacity',
            'tier': self.tier_panel.build(
                {
                    'tenant_id': tenant_id,
                    'active_tier': normalized.get('active_tier'),
                    'reason': normalized.get('reason'),
                }
            ),
            'queue_pressure': self.queue_pressure_panel.build(
                {
                    'tenant_id': tenant_id,
                    'queue_depth': normalized.get('queue_depth'),
                    'backlog_age_seconds': normalized.get('backlog_age_seconds'),
                }
            ),
            'provider_health': self.provider_health_panel.build(
                {
                    'tenant_id': tenant_id,
                    'providers': tuple(normalized.get('providers', ()) or ()),
                }
            ),
            'read_only': True,
        }
