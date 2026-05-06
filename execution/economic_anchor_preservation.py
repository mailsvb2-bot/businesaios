from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

CANON_ECONOMIC_ANCHOR_PRESERVATION = True


def _safe_dict(value: object) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


@dataclass(frozen=True, slots=True)
class EconomicAnchorPreservationVerdict:
    preserved: bool
    missing_anchor_ids: tuple[str, ...] = ()
    reason: str = 'economic_anchor_preserved'
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            'preserved': bool(self.preserved),
            'missing_anchor_ids': list(self.missing_anchor_ids),
            'reason': self.reason,
            'metadata': dict(self.metadata),
        }


class EconomicAnchorPreservationChecker:
    def validate(
        self,
        *,
        payload: Mapping[str, Any],
        required_anchor_ids: list[str] | tuple[str, ...] = (),
    ) -> EconomicAnchorPreservationVerdict:
        normalized = _safe_dict(payload)
        seen_ids: set[str] = set()

        for segment in ('feedback_rows', 'roi_rows', 'snapshot_rows', 'trace_rows'):
            for row in normalized.get(segment) or ():
                item = _safe_dict(row)
                for key in ('event_id', 'snapshot_id', 'trace_id'):
                    value = str(item.get(key) or '')
                    if value:
                        seen_ids.add(value)

        missing = [anchor for anchor in required_anchor_ids if anchor and anchor not in seen_ids]
        return EconomicAnchorPreservationVerdict(
            preserved=not missing,
            missing_anchor_ids=tuple(missing),
            reason='economic_anchor_preserved' if not missing else 'economic_anchor_missing_after_pruning',
            metadata={'owner': 'execution.economic_anchor_preservation'},
        )


__all__ = [
    'CANON_ECONOMIC_ANCHOR_PRESERVATION',
    'EconomicAnchorPreservationVerdict',
    'EconomicAnchorPreservationChecker',
]
