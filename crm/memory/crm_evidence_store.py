from __future__ import annotations

from crm.memory.crm_action_evidence import CrmActionEvidence
from crm.memory.crm_outcome_evidence import CrmOutcomeEvidence


class InMemoryCrmEvidenceStore:
    def __init__(self) -> None:
        self.action_events: list[CrmActionEvidence] = []
        self.outcome_events: list[CrmOutcomeEvidence] = []

    def append_action(self, evidence: CrmActionEvidence) -> None:
        self.action_events.append(evidence)

    def append_outcome(self, evidence: CrmOutcomeEvidence) -> None:
        self.outcome_events.append(evidence)
