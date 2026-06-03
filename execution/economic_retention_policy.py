from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any
from collections.abc import Mapping

from execution.economic_anchor_preservation import EconomicAnchorPreservationChecker

CANON_ECONOMIC_RETENTION_POLICY = True


SEGMENT_KEYS = (
    'feedback_rows',
    'roi_rows',
    'snapshot_rows',
    'trace_rows',
    'metrics_rows',
)

_SEGMENT_TIMESTAMP_FIELDS: dict[str, tuple[str, ...]] = {
    'feedback_rows': ('created_at', 'updated_at', 'event_at'),
    'roi_rows': ('created_at', 'updated_at', 'event_at'),
    'snapshot_rows': ('created_at', 'captured_at', 'snapshot_at'),
    'trace_rows': ('created_at', 'captured_at', 'trace_at'),
    'metrics_rows': ('created_at', 'captured_at', 'snapshot_at'),
}


def _safe_dict(value: object) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _safe_int(value: object, *, default: int = 0) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return int(default)
    return max(0, int(parsed))


def _safe_datetime(value: object) -> datetime | None:
    if isinstance(value, datetime):
        return value.astimezone(UTC) if value.tzinfo is not None else value.replace(tzinfo=UTC)
    text = str(value or '').strip()
    if not text:
        return None
    try:
        normalized = text.replace('Z', '+00:00')
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    return parsed.astimezone(UTC) if parsed.tzinfo is not None else parsed.replace(tzinfo=UTC)


def _now_utc() -> datetime:
    return datetime.now(UTC)


def _segment_age_days(raw: dict[str, Any], segment: str, default: int | None) -> int | None:
    key = f'max_{segment.removesuffix("_rows")}_age_days'
    if key in raw:
        value = _safe_int(raw.get(key), default=0)
        return value if value > 0 else None
    return default


def _row_timestamp(row: Mapping[str, Any], *, segment: str) -> datetime | None:
    payload = _safe_dict(row)
    for field_name in _SEGMENT_TIMESTAMP_FIELDS.get(segment, ()): 
        parsed = _safe_datetime(payload.get(field_name))
        if parsed is not None:
            return parsed
    metadata = _safe_dict(payload.get('metadata'))
    for field_name in _SEGMENT_TIMESTAMP_FIELDS.get(segment, ()): 
        parsed = _safe_datetime(metadata.get(field_name))
        if parsed is not None:
            return parsed
    return None


@dataclass(frozen=True, slots=True)
class EconomicRetentionPolicy:
    max_feedback_rows: int = 250
    max_roi_rows: int = 250
    max_snapshot_rows: int = 250
    max_trace_rows: int = 250
    max_metrics_rows: int = 250
    max_age_days: int | None = None
    max_feedback_age_days: int | None = None
    max_roi_age_days: int | None = None
    max_snapshot_age_days: int | None = None
    max_trace_age_days: int | None = None
    max_metrics_age_days: int | None = None
    preserve_audit_summary: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any] | None) -> 'EconomicRetentionPolicy':
        raw = _safe_dict(payload)
        max_age_days = _safe_int(raw.get('max_age_days'), default=0)
        default_age = max_age_days if max_age_days > 0 else None
        return cls(
            max_feedback_rows=_safe_int(raw.get('max_feedback_rows'), default=250),
            max_roi_rows=_safe_int(raw.get('max_roi_rows'), default=250),
            max_snapshot_rows=_safe_int(raw.get('max_snapshot_rows'), default=250),
            max_trace_rows=_safe_int(raw.get('max_trace_rows'), default=250),
            max_metrics_rows=_safe_int(raw.get('max_metrics_rows'), default=250),
            max_age_days=default_age,
            max_feedback_age_days=_segment_age_days(raw, 'feedback_rows', default_age),
            max_roi_age_days=_segment_age_days(raw, 'roi_rows', default_age),
            max_snapshot_age_days=_segment_age_days(raw, 'snapshot_rows', default_age),
            max_trace_age_days=_segment_age_days(raw, 'trace_rows', default_age),
            max_metrics_age_days=_segment_age_days(raw, 'metrics_rows', default_age),
            preserve_audit_summary=bool(raw.get('preserve_audit_summary', True)),
            metadata=_safe_dict(raw.get('metadata')),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            'max_feedback_rows': int(self.max_feedback_rows),
            'max_roi_rows': int(self.max_roi_rows),
            'max_snapshot_rows': int(self.max_snapshot_rows),
            'max_trace_rows': int(self.max_trace_rows),
            'max_metrics_rows': int(self.max_metrics_rows),
            'max_age_days': self.max_age_days,
            'max_feedback_age_days': self.max_feedback_age_days,
            'max_roi_age_days': self.max_roi_age_days,
            'max_snapshot_age_days': self.max_snapshot_age_days,
            'max_trace_age_days': self.max_trace_age_days,
            'max_metrics_age_days': self.max_metrics_age_days,
            'preserve_audit_summary': bool(self.preserve_audit_summary),
            'metadata': dict(self.metadata),
        }

    def age_limit_for_segment(self, segment: str) -> int | None:
        specific = {
            'feedback_rows': self.max_feedback_age_days,
            'roi_rows': self.max_roi_age_days,
            'snapshot_rows': self.max_snapshot_age_days,
            'trace_rows': self.max_trace_age_days,
            'metrics_rows': self.max_metrics_age_days,
        }.get(segment)
        return specific if specific is not None else self.max_age_days


@dataclass(frozen=True, slots=True)
class EconomicRetentionApplication:
    payload: dict[str, Any]
    retention: dict[str, Any] = field(default_factory=dict)



def apply_economic_retention_policy(
    *,
    payload: Mapping[str, Any],
    retention_policy: EconomicRetentionPolicy,
    reference_time: datetime | None = None,
) -> EconomicRetentionApplication:
    data = _safe_dict(payload)
    limits = {
        'feedback_rows': retention_policy.max_feedback_rows,
        'roi_rows': retention_policy.max_roi_rows,
        'snapshot_rows': retention_policy.max_snapshot_rows,
        'trace_rows': retention_policy.max_trace_rows,
        'metrics_rows': retention_policy.max_metrics_rows,
    }
    reference = reference_time.astimezone(UTC) if reference_time is not None and reference_time.tzinfo is not None else reference_time.replace(tzinfo=UTC) if isinstance(reference_time, datetime) else _now_utc()
    normalized: dict[str, Any] = {key: value for key, value in data.items() if key not in SEGMENT_KEYS}
    retention_summary: dict[str, Any] = {
        'owner': 'execution.economic_retention_policy',
        'policy': retention_policy.to_dict(),
        'applied_at': reference.isoformat(),
        'segments': {},
    }
    for segment in SEGMENT_KEYS:
        rows = [dict(row) for row in (data.get(segment) or ())]
        age_limit_days = retention_policy.age_limit_for_segment(segment)
        age_cutoff = reference - timedelta(days=age_limit_days) if age_limit_days is not None else None
        age_retained_rows: list[dict[str, Any]] = []
        age_dropped_count = 0
        for row in rows:
            if age_cutoff is None:
                age_retained_rows.append(row)
                continue
            row_time = _row_timestamp(row, segment=segment)
            if row_time is None or row_time >= age_cutoff:
                age_retained_rows.append(row)
            else:
                age_dropped_count += 1
        limit = int(limits[segment])
        retained_rows = age_retained_rows[-limit:] if limit > 0 else []
        normalized[segment] = retained_rows
        retention_summary['segments'][segment] = {
            'original_count': len(rows),
            'age_retained_count': len(age_retained_rows),
            'retained_count': len(retained_rows),
            'dropped_count': max(0, len(rows) - len(retained_rows)),
            'age_dropped_count': age_dropped_count,
            'count_dropped_after_age_filter': max(0, len(age_retained_rows) - len(retained_rows)),
            'age_limit_days': age_limit_days,
        }
    if retention_policy.preserve_audit_summary:
        normalized['audit_summary'] = dict(_safe_dict(data.get('audit_summary')))
    else:
        normalized['audit_summary'] = {}
    metadata = _safe_dict(normalized.get('metadata'))
    metadata['retention'] = retention_summary
    anchor_verdict = EconomicAnchorPreservationChecker().validate(
        payload=normalized,
        required_anchor_ids=tuple(_safe_dict(normalized.get('metadata')).get('required_anchor_ids') or ()),
    )
    metadata['anchor_preservation'] = anchor_verdict.to_dict()
    if not anchor_verdict.preserved:
        metadata['retention_warning'] = 'economic_anchor_missing_after_pruning'
    normalized['metadata'] = metadata
    return EconomicRetentionApplication(payload=normalized, retention=retention_summary)


__all__ = [
    'CANON_ECONOMIC_RETENTION_POLICY',
    'EconomicRetentionPolicy',
    'EconomicRetentionApplication',
    'apply_economic_retention_policy',
]
