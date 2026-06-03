from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from collections.abc import Mapping

CANON_ECONOMIC_SEGMENT_VALIDATION = True

_REQUIRED_SEGMENTS = (
    'feedback_rows',
    'roi_rows',
    'snapshot_rows',
    'trace_rows',
    'metrics_rows',
    'export_manifest',
)


def _safe_dict(value: object) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


@dataclass(frozen=True, slots=True)
class EconomicSegmentValidationVerdict:
    complete: bool
    missing_segments: tuple[str, ...] = ()
    empty_required_segments: tuple[str, ...] = ()
    reason: str = 'economic_segments_complete'
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            'complete': bool(self.complete),
            'missing_segments': list(self.missing_segments),
            'empty_required_segments': list(self.empty_required_segments),
            'reason': self.reason,
            'metadata': dict(self.metadata),
        }


class EconomicSegmentValidator:
    def validate(self, *, payload: Mapping[str, Any]) -> EconomicSegmentValidationVerdict:
        normalized = _safe_dict(payload)
        missing = [name for name in _REQUIRED_SEGMENTS if name not in normalized]
        empty_required = [
            name for name in ('snapshot_rows', 'trace_rows', 'export_manifest')
            if name in normalized and not normalized.get(name)
        ]
        ok = not missing and not empty_required
        return EconomicSegmentValidationVerdict(
            complete=ok,
            missing_segments=tuple(missing),
            empty_required_segments=tuple(empty_required),
            reason='economic_segments_complete' if ok else 'economic_segments_incomplete',
            metadata={'owner': 'execution.economic_segment_validation'},
        )


__all__ = [
    'CANON_ECONOMIC_SEGMENT_VALIDATION',
    'EconomicSegmentValidationVerdict',
    'EconomicSegmentValidator',
]
