from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from advisory.revenue_os.contracts import RevenueDecisionIntent

CANON_ADVISORY_REVENUE_OS_APPROVAL_POLICY = True


@dataclass(frozen=True, slots=True)
class ApprovalSummary:
    approval_required_count: int
    approval_required_action_types: tuple[str, ...]
    highest_blast_radius: str

    def to_dict(self) -> dict[str, object]:
        return {
            'approval_required_count': self.approval_required_count,
            'approval_required_action_types': list(self.approval_required_action_types),
            'highest_blast_radius': self.highest_blast_radius,
        }


class RevenueApprovalPolicy:
    _order = {'low': 0, 'moderate': 1, 'high': 2}

    def summarize(self, intents: Iterable[RevenueDecisionIntent]) -> ApprovalSummary:
        normalized = tuple(item.normalized_copy() for item in intents)
        requiring = tuple(item for item in normalized if item.requires_approval)
        highest = 'low'
        if normalized:
            highest = max((item.blast_radius for item in normalized), key=self._order.__getitem__)
        return ApprovalSummary(
            approval_required_count=len(requiring),
            approval_required_action_types=tuple(sorted({item.action_type for item in requiring})),
            highest_blast_radius=highest,
        )


__all__ = ['ApprovalSummary', 'CANON_ADVISORY_REVENUE_OS_APPROVAL_POLICY', 'RevenueApprovalPolicy']
