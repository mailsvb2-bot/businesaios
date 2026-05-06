from __future__ import annotations
from dataclasses import dataclass
from typing import Iterable
from execution.verification.evidence_types import EvidenceItem
CANON_EVIDENCE_CORRELATION = True
@dataclass(frozen=True, slots=True)
class EvidenceCorrelationGroup:
    correlation_key: str
    evidence: tuple[EvidenceItem, ...]
    has_positive: bool
    has_negative: bool
    has_pending: bool
    has_authoritative: bool
    @property
    def conflicting(self) -> bool:
        return self.has_positive and self.has_negative
    def to_dict(self) -> dict[str, object]:
        return {
            "correlation_key": self.correlation_key,
            "evidence": [item.to_dict() for item in self.evidence],
            "has_positive": self.has_positive,
            "has_negative": self.has_negative,
            "has_pending": self.has_pending,
            "has_authoritative": self.has_authoritative,
            "conflicting": self.conflicting,
        }
@dataclass(frozen=True, slots=True)
class EvidenceCorrelationResult:
    groups: tuple[EvidenceCorrelationGroup, ...]
    matched_evidence: tuple[EvidenceItem, ...]
    conflicting_evidence: tuple[EvidenceItem, ...]
    orphan_evidence: tuple[EvidenceItem, ...]
    duplicate_evidence_ids: tuple[str, ...]
    def to_dict(self) -> dict[str, object]:
        return {
            "groups": [group.to_dict() for group in self.groups],
            "matched_evidence": [item.to_dict() for item in self.matched_evidence],
            "conflicting_evidence": [item.to_dict() for item in self.conflicting_evidence],
            "orphan_evidence": [item.to_dict() for item in self.orphan_evidence],
            "duplicate_evidence_ids": list(self.duplicate_evidence_ids),
        }
class EvidenceCorrelation:
    def deduplicate(self, evidence: Iterable[EvidenceItem]) -> tuple[tuple[EvidenceItem, ...], tuple[str, ...]]:
        seen: set[str] = set()
        unique: list[EvidenceItem] = []
        duplicates: list[str] = []
        for item in evidence:
            if item.evidence_id in seen:
                duplicates.append(item.evidence_id)
                continue
            seen.add(item.evidence_id)
            unique.append(item)
        return tuple(unique), tuple(duplicates)
    def correlate(self, evidence: Iterable[EvidenceItem]) -> EvidenceCorrelationResult:
        items, duplicates = self.deduplicate(evidence)
        buckets: dict[str, list[EvidenceItem]] = {}
        for item in items:
            buckets.setdefault(item.correlation_key(), []).append(item)
        groups: list[EvidenceCorrelationGroup] = []
        matched: list[EvidenceItem] = []
        conflicting: list[EvidenceItem] = []
        orphan: list[EvidenceItem] = []
        for key, rows in sorted(buckets.items()):
            group = EvidenceCorrelationGroup(
                correlation_key=key,
                evidence=tuple(rows),
                has_positive=any(item.is_positive() for item in rows),
                has_negative=any(item.is_negative() for item in rows),
                has_pending=any(item.is_pending() for item in rows),
                has_authoritative=any(item.is_authoritative() for item in rows),
            )
            groups.append(group)
            if len(rows) == 1 and not rows[0].external_refs:
                orphan.append(rows[0])
            if group.conflicting:
                conflicting.extend(rows)
            elif group.has_positive or group.has_pending:
                matched.extend(rows)
        return EvidenceCorrelationResult(
            groups=tuple(groups),
            matched_evidence=tuple(matched),
            conflicting_evidence=tuple(conflicting),
            orphan_evidence=tuple(orphan),
            duplicate_evidence_ids=duplicates,
        )
__all__ = [
    "CANON_EVIDENCE_CORRELATION",
    "EvidenceCorrelationGroup",
    "EvidenceCorrelationResult",
    "EvidenceCorrelation",
]
