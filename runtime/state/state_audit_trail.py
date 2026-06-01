from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from runtime.state.state_contract import StateSynthesisRequest, StateSynthesizedSnapshot

CANON_STATE_AUDIT_TRAIL = True


@dataclass
class FileStateAuditTrail:
    path: Path

    def __post_init__(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def record(self, *, request: StateSynthesisRequest, snapshot: StateSynthesizedSnapshot) -> None:
        row = {
            "state_id": snapshot.state_id,
            "tenant_id": snapshot.tenant_id,
            "business_id": snapshot.business_id,
            "synthesized_at_ms": snapshot.synthesized_at_ms,
            "correlation_id": request.correlation_id,
            "observation_count": len(request.observations),
            "field_count": len(snapshot.fields),
            "conflict_count": len(snapshot.conflicts),
            "sources": sorted({str(item.source) for item in request.observations}),
            "meta": dict(request.meta),
        }

        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
