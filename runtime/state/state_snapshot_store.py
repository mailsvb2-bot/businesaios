from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from runtime.state.state_contract import (
    StateConflictRecord,
    StateEvidenceRef,
    StateFieldRecord,
    StateSynthesizedSnapshot,
)

CANON_STATE_SNAPSHOT_STORE = True


@dataclass
class FileStateSnapshotStore:
    root_dir: Path

    def __post_init__(self) -> None:
        self.root_dir.mkdir(parents=True, exist_ok=True)

    def load_latest(self, *, tenant_id: str, business_id: str) -> StateSynthesizedSnapshot | None:
        path = self._path(tenant_id=tenant_id, business_id=business_id)
        if not path.exists():
            return None
        return snapshot_from_dict(json.loads(path.read_text(encoding="utf-8")))

    def save_snapshot(self, snapshot: StateSynthesizedSnapshot) -> None:
        path = self._path(tenant_id=snapshot.tenant_id, business_id=snapshot.business_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(snapshot.to_dict(), ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")

    def _path(self, *, tenant_id: str, business_id: str) -> Path:
        return self.root_dir / str(tenant_id) / f"{business_id}.json"


def snapshot_from_dict(payload: dict[str, Any]) -> StateSynthesizedSnapshot:
    fields = {
        str(key): StateFieldRecord(
            field_path=str(value["field_path"]),
            value=value.get("value"),
            value_kind=str(value.get("value_kind") or "known"),
            source=str(value.get("source") or ""),
            observed_at_ms=int(value.get("observed_at_ms") or 0),
            recorded_at_ms=int(value.get("recorded_at_ms") or value.get("observed_at_ms") or 0),
            freshness_status=str(value.get("freshness_status") or "fresh"),
            freshness_reason=str(value.get("freshness_reason") or ""),
            confidence=float(value.get("confidence") if value.get("confidence") is not None else 0.0),
            source_priority=int(value.get("source_priority") or 0),
            authoritative=bool(value.get("authoritative")),
            provenance_hash=str(value.get("provenance_hash") or ""),
            evidence_refs=tuple(
                StateEvidenceRef(
                    evidence_id=str(item.get("evidence_id") or ""),
                    kind=str(item.get("kind") or "external"),
                    uri=str(item.get("uri") or ""),
                    checksum=str(item.get("checksum") or ""),
                    observed_at_ms=int(item.get("observed_at_ms") or 0),
                    meta=dict(item.get("meta") or {}),
                )
                for item in value.get("evidence_refs") or []
            ),
            candidates_considered=int(value.get("candidates_considered") or 1),
            conflict=bool(value.get("conflict")),
            meta=dict(value.get("meta") or {}),
        )
        for key, value in dict(payload.get("fields") or {}).items()
    }

    conflicts = tuple(
        StateConflictRecord(
            field_path=str(item.get("field_path") or ""),
            chosen_source=str(item.get("chosen_source") or ""),
            chosen_provenance_hash=str(item.get("chosen_provenance_hash") or ""),
            candidate_sources=tuple(str(x) for x in item.get("candidate_sources") or ()),
            reason=str(item.get("reason") or ""),
            conflict_kind=str(item.get("conflict_kind") or "multi_source"),
        )
        for item in payload.get("conflicts") or []
    )

    return StateSynthesizedSnapshot(
        state_id=str(payload.get("state_id") or ""),
        tenant_id=str(payload.get("tenant_id") or ""),
        business_id=str(payload.get("business_id") or ""),
        synthesized_at_ms=int(payload.get("synthesized_at_ms") or 0),
        schema_version=str(payload.get("schema_version") or "state_synthesis@v1"),
        values=dict(payload.get("values") or {}),
        fields=fields,
        conflicts=conflicts,
        source_watermarks={str(key): int(value) for key, value in dict(payload.get("source_watermarks") or {}).items()},
        audit=dict(payload.get("audit") or {}),
        meta=dict(payload.get("meta") or {}),
    )
