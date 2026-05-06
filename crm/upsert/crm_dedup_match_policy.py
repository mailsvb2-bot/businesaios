from __future__ import annotations

from crm.crm_dedup_contract import CrmDedupMatch


class CrmDedupMatchPolicy:
    def evaluate(self, *, existing_record_id: str | None, dedup_key: str) -> CrmDedupMatch:
        if existing_record_id:
            return CrmDedupMatch(matched=True, record_id=existing_record_id, confidence=0.99, reason=f'dedup_key:{dedup_key}')
        return CrmDedupMatch(matched=False, record_id=None, confidence=0.0, reason='not_found')
