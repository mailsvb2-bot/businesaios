from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from runtime.state.state_contract import StateSynthesizedSnapshot


CANON_STATE_DELTA_LOG = True


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
            if previous_field is None:
                change_kind = "created"
            elif previous_field.provenance_hash != field.provenance_hash:
                change_kind = "updated"
            else:
                change_kind = "unchanged"

            deltas.append(
                {
                    "field_path": field_path,
                    "change_kind": change_kind,
                    "previous_provenance_hash": None if previous_field is None else previous_field.provenance_hash,
                    "current_provenance_hash": field.provenance_hash,
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
