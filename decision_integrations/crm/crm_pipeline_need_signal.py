from __future__ import annotations


class CrmPipelineNeedSignal:
    def build(self, **kwargs) -> dict[str, object]:
        crm_state = dict(kwargs.get('crm_state') or {})
        lead_score = int(kwargs.get('lead_score') or 0)
        return {'signal_name': 'CrmPipelineNeedSignal', 'value': crm_state.get("open_deals", 0) == 0}
