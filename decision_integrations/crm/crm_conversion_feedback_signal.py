from __future__ import annotations


class CrmConversionFeedbackSignal:
    def build(self, **kwargs) -> dict[str, object]:
        crm_state = dict(kwargs.get('crm_state') or {})
        lead_score = int(kwargs.get('lead_score') or 0)
        return {'signal_name': 'CrmConversionFeedbackSignal', 'value': crm_state.get("recent_conversions", 0)}
