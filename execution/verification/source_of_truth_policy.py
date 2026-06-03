from __future__ import annotations
from dataclasses import dataclass
from collections.abc import Iterable
from execution.verification.evidence_types import EvidenceItem
CANON_SOURCE_OF_TRUTH_POLICY = True
def _priority(item: EvidenceItem) -> tuple[int, float, float]:
    kind_rank = {
        "callback": 500,
        "ledger_entry": 450,
        "connector_snapshot": 400,
        "router_result": 300,
        "operator_confirmation": 200,
        "execution_receipt": 100,
        "unknown": 0,
    }.get(item.kind, 0)
    positivity_rank = 2.0 if item.is_positive() else (1.0 if item.is_pending() else 0.0)
    return kind_rank, positivity_rank, float(item.confidence)
@dataclass(frozen=True, slots=True)
class SourceOfTruthResolution:
    source_of_truth: str
    leader_evidence_id: str
    authoritative_evidence: tuple[EvidenceItem, ...]
    authoritative_positive_evidence: tuple[EvidenceItem, ...]
    authoritative_negative_evidence: tuple[EvidenceItem, ...]
    positive_evidence: tuple[EvidenceItem, ...]
    negative_evidence: tuple[EvidenceItem, ...]
    pending_evidence: tuple[EvidenceItem, ...]
    conflict_detected: bool
    def to_dict(self) -> dict[str, object]:
        return {
            "source_of_truth": self.source_of_truth,
            "leader_evidence_id": self.leader_evidence_id,
            "authoritative_evidence": [item.to_dict() for item in self.authoritative_evidence],
            "authoritative_positive_evidence": [item.to_dict() for item in self.authoritative_positive_evidence],
            "authoritative_negative_evidence": [item.to_dict() for item in self.authoritative_negative_evidence],
            "positive_evidence": [item.to_dict() for item in self.positive_evidence],
            "negative_evidence": [item.to_dict() for item in self.negative_evidence],
            "pending_evidence": [item.to_dict() for item in self.pending_evidence],
            "conflict_detected": self.conflict_detected,
        }
class SourceOfTruthPolicy:
    def resolve(self, evidence: Iterable[EvidenceItem]) -> SourceOfTruthResolution:
        items = tuple(evidence)
        positive = tuple(item for item in items if item.is_positive())
        negative = tuple(item for item in items if item.is_negative())
        pending = tuple(item for item in items if item.is_pending())
        authoritative = tuple(sorted((item for item in items if item.is_authoritative()), key=_priority, reverse=True))
        authoritative_positive = tuple(item for item in authoritative if item.is_positive())
        authoritative_negative = tuple(item for item in authoritative if item.is_negative())
        leader: EvidenceItem | None = None
        if authoritative_positive:
            leader = authoritative_positive[0]
        elif authoritative:
            leader = authoritative[0]
        elif positive:
            leader = sorted(positive, key=_priority, reverse=True)[0]
        elif pending:
            leader = sorted(pending, key=_priority, reverse=True)[0]
        elif negative:
            leader = sorted(negative, key=_priority, reverse=True)[0]
        source = (leader.source or leader.kind) if leader is not None else "none"
        leader_evidence_id = leader.evidence_id if leader is not None else ""
        conflict_detected = bool(authoritative_positive and authoritative_negative)
        return SourceOfTruthResolution(
            source_of_truth=source,
            leader_evidence_id=leader_evidence_id,
            authoritative_evidence=authoritative,
            authoritative_positive_evidence=authoritative_positive,
            authoritative_negative_evidence=authoritative_negative,
            positive_evidence=positive,
            negative_evidence=negative,
            pending_evidence=pending,
            conflict_detected=conflict_detected,
        )
__all__ = ["CANON_SOURCE_OF_TRUTH_POLICY", "SourceOfTruthResolution", "SourceOfTruthPolicy"]
