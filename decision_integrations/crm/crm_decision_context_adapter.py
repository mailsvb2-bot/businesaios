from __future__ import annotations


class CrmDecisionContextAdapter:
    def enrich(self, decision_context: dict[str, object], crm_context: dict[str, object]) -> dict[str, object]:
        payload = dict(decision_context)
        payload['crm'] = dict(crm_context)
        return payload
