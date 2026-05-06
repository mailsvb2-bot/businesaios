from __future__ import annotations


class CrmExecutionResultMapper:
    def map(self, payload: dict[str, object]) -> dict[str, object]:
        return {'channel': 'crm', **payload}
