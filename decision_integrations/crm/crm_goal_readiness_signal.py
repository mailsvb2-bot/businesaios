from __future__ import annotations


class CrmGoalReadinessSignal:
    def build(self, **kwargs) -> dict[str, object]:
        crm_state = dict(kwargs.get('crm_state') or {})
        lead_score = int(kwargs.get('lead_score') or 0)
        return {'signal_name': 'CrmGoalReadinessSignal', 'value': crm_state.get("funnel_health") == "healthy"}
