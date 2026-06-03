from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from collections.abc import Iterable, Mapping


CANON_INFERENCE_FAIRNESS_SCHEDULER = True


@dataclass(frozen=True)
class InferenceFairnessSlot:
    tenant_id: str
    queue_depth: int
    allocated_share: float


class InferenceFairnessScheduler:
    def allocate(self, rows: Iterable[Mapping[str, object]]) -> tuple[InferenceFairnessSlot, ...]:
        normalized: dict[str, int] = defaultdict(int)
        for row in rows:
            tenant_id = str(row.get('tenant_id') or '').strip()
            if not tenant_id:
                continue
            try:
                queue_depth = max(0, int(row.get('queue_depth') or 0))
            except (TypeError, ValueError):
                queue_depth = 0
            normalized[tenant_id] += queue_depth
        if not normalized:
            return ()
        total = sum(max(1, value) for value in normalized.values())
        return tuple(
            InferenceFairnessSlot(
                tenant_id=tenant_id,
                queue_depth=queue_depth,
                allocated_share=round(max(1, queue_depth) / total, 6),
            )
            for tenant_id, queue_depth in sorted(normalized.items())
        )
