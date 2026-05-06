from __future__ import annotations

from crm.memory.crm_evidence_store import InMemoryCrmEvidenceStore


class CrmMemoryProjection:
    def summarize(self, store: InMemoryCrmEvidenceStore) -> dict[str, object]:
        return {
            'verified_action_count': sum(1 for event in store.action_events if event.verified),
            'outcome_signal_count': len(store.outcome_events),
        }
