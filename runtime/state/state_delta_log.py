from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from runtime.state.state_contract import StateFieldRecord, StateSynthesizedSnapshot

CANON_STATE_DELTA_LOG = True


def _lifecycle_state(field: StateFieldRecord) -> dict[str, object]:
    return {
        "value_kind": str(field.value_kind),
        "freshness_status": str(field.freshness_status),
        "freshness_reason": str(field.freshness_reason),
        "valid_from_ms": field.valid_from_ms,
        "valid_until_ms": field.valid_until_ms,
        "superseded_at_ms": field.superseded_at_ms,
        "conflict": bool(field.conflict),
        "conflict_status": field.meta.get("conflict_status"),
        "resolution_policy": field.meta.get("resolution_policy"),
        "superseded_by_business_fact_id": field.meta.get("superseded_by_business_fact_id"),
    }


@dataclass
class FileStateDeltaLog:
    path: Path

    def __post_init__(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def append(self, *, previous: StateSynthesizedSnapshot | None, current: StateSynthesizedSnapshot) -> None:
        deltas = []
        previous_fields = {} if previous is None else previous.fields

        for field_path, field in current.fields.items():
            previous_field = previous_fields.get(field_path)
            previous_lifecycle = None if previous_field is None else _lifecycle_state(previous_field)
            current_lifecycle = _lifecycle_state(field)
            if previous_field is None:
                change_kind = "created"
                change_reason = "new_field"
            elif previous_field.provenance_hash != field.provenance_hash:
                change_kind = "updated"
                change_reason = "provenance"
            elif previous_lifecycle != current_lifecycle:
                change_kind = "updated"
                change_reason = "lifecycle"
            else:
                change_kind = "unchanged"
                change_reason = "none"

            deltas.append(
                {
                    "field_path": field_path,
                    "change_kind": change_kind,
                    "change_reason": change_reason,
                    "previous_provenance_hash": None if previous_field is None else previous_field.provenance_hash,
                    "current_provenance_hash": field.provenance_hash,
                    "previous_lifecycle": previous_lifecycle,
                    "current_lifecycle": current_lifecycle,
                    "observed_at_ms": field.observed_at_ms,
                    "source": field.source,
                }
            )

        for field_path, field in previous_fields.items():
            if field_path not in current.fields:
                deltas.append(
                    {
                        "field_path": field_path,
                        "change_kind": "deleted",
                        "previous_provenance_hash": field.provenance_hash,
                        "current_provenance_hash": None,
                        "observed_at_ms": field.observed_at_ms,
                        "source": field.source,
                    }
                )

        record = {
            "state_id": current.state_id,
            "tenant_id": current.tenant_id,
            "business_id": current.business_id,
            "synthesized_at_ms": current.synthesized_at_ms,
            "delta_count": len(deltas),
            "deltas": deltas,
        }

        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
