from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

from app.web.components.capacity_budget_panel import CapacityBudgetPanel
from app.web.components.escalation_history_panel import EscalationHistoryPanel
from app.web.components.inference_verification_panel import InferenceVerificationPanel
from app.web.components.manual_capacity_override_panel import ManualCapacityOverridePanel
from app.web.components.provider_mix_panel import ProviderMixPanel
from core.tenancy.normalization import require_tenant_id


CANON_WEB_INFERENCE_RUNTIME_ADMIN_PAGE = True


@dataclass(frozen=True, slots=True)
class InferenceRuntimeAdminPage:
    budget_panel: CapacityBudgetPanel = field(default_factory=CapacityBudgetPanel)
    provider_mix_panel: ProviderMixPanel = field(default_factory=ProviderMixPanel)
    verification_panel: InferenceVerificationPanel = field(default_factory=InferenceVerificationPanel)
    escalation_history_panel: EscalationHistoryPanel = field(default_factory=EscalationHistoryPanel)
    manual_override_panel: ManualCapacityOverridePanel = field(default_factory=ManualCapacityOverridePanel)

    def build(self, payload: Mapping[str, Any] | None) -> dict[str, Any]:
        normalized = dict(payload or {})
        tenant_id = require_tenant_id(normalized.get('tenant_id'))
        return {
            'tenant_id': tenant_id,
            'title': 'Inference Runtime Admin',
            'budget': self.budget_panel.build(
                {
                    'tenant_id': tenant_id,
                    'headroom_usd': normalized.get('headroom_usd'),
                    'burn_rate_usd_per_hour': normalized.get('burn_rate_usd_per_hour'),
                }
            ),
            'provider_mix': self.provider_mix_panel.build(
                {
                    'tenant_id': tenant_id,
                    'providers': tuple(normalized.get('provider_mix', ()) or ()),
                }
            ),
            'verification': self.verification_panel.build(
                {
                    'tenant_id': tenant_id,
                    **dict(normalized.get('verification_summary', {}) or {}),
                }
            ),
            'escalation_history': self.escalation_history_panel.build(
                {
                    'tenant_id': tenant_id,
                    'events': tuple(normalized.get('recent_escalations', ()) or ()),
                }
            ),
            'manual_override': self.manual_override_panel.build(
                {
                    'tenant_id': tenant_id,
                    'frozen': normalized.get('frozen', False),
                    'active_tier': normalized.get('active_tier'),
                }
            ),
            'read_only': True,
        }
