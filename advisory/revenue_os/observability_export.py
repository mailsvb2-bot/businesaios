from __future__ import annotations

from typing import Iterable

from advisory.revenue_os.audit_events import RevenueAuditEvent

CANON_ADVISORY_REVENUE_OS_OBSERVABILITY_EXPORT = True


class RevenueObservabilityExporter:
    def build_records(self, events: Iterable[RevenueAuditEvent]) -> tuple[dict[str, object], ...]:
        return tuple(item.normalized_copy().to_record() for item in events)


__all__ = ['CANON_ADVISORY_REVENUE_OS_OBSERVABILITY_EXPORT', 'RevenueObservabilityExporter']
