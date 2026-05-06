from __future__ import annotations

CANON_COMPAT_SHIM = True

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping, Protocol


CANON_ECONOMIC_POLICY_SNAPSHOT_STORE = True


def _safe_dict(value: object) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


@dataclass(frozen=True, slots=True)
class EconomicPolicySnapshotRecord:
    payload: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return dict(self.payload)


class EconomicPolicySnapshotStore(Protocol):
    @property
    def path(self) -> Path: ...

    def append(self, row: EconomicPolicySnapshotRecord) -> None: ...
    def append_payload(self, payload: Mapping[str, Any]) -> EconomicPolicySnapshotRecord: ...
    def list_rows(self) -> tuple[EconomicPolicySnapshotRecord, ...]: ...


class NoOpEconomicPolicySnapshotStore:
    def append(self, row: EconomicPolicySnapshotRecord) -> None:
        return None

    def append_payload(self, payload: Mapping[str, Any]) -> EconomicPolicySnapshotRecord:
        return EconomicPolicySnapshotRecord(payload=dict(payload))

    def list_rows(self) -> tuple[EconomicPolicySnapshotRecord, ...]:
        return ()


class InMemoryEconomicPolicySnapshotStore:
    def __init__(self) -> None:
        self._rows: dict[str, EconomicPolicySnapshotRecord] = {}
        self._order: list[str] = []

    def append(self, row: EconomicPolicySnapshotRecord) -> None:
        snapshot_id = str(row.payload.get('snapshot_id') or '')
        if snapshot_id and snapshot_id not in self._rows:
            self._order.append(snapshot_id)
        if snapshot_id:
            self._rows[snapshot_id] = row
        else:
            synthetic = str(len(self._order))
            self._order.append(synthetic)
            self._rows[synthetic] = row

    def append_payload(self, payload: Mapping[str, Any]) -> EconomicPolicySnapshotRecord:
        row = EconomicPolicySnapshotRecord(payload=dict(payload))
        self.append(row)
        return row

    def list_rows(self) -> tuple[EconomicPolicySnapshotRecord, ...]:
        return tuple(self._rows[key] for key in self._order if key in self._rows)


class JsonlEconomicPolicySnapshotStore:
    def __init__(self, path: str | Path) -> None:
        self._path = Path(path)

    @property
    def path(self) -> Path:
        return self._path

    def append(self, row: EconomicPolicySnapshotRecord) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with self._path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(row.to_dict(), ensure_ascii=False, sort_keys=True))
            handle.write("\n")

    def append_payload(self, payload: Mapping[str, Any]) -> EconomicPolicySnapshotRecord:
        row = EconomicPolicySnapshotRecord(payload=dict(payload))
        self.append(row)
        return row

    def list_rows(self) -> tuple[EconomicPolicySnapshotRecord, ...]:
        if not self._path.exists():
            return ()
        rows: list[EconomicPolicySnapshotRecord] = []
        with self._path.open('r', encoding='utf-8') as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                rows.append(EconomicPolicySnapshotRecord(payload=_safe_dict(json.loads(line))))
        dedup: dict[str, EconomicPolicySnapshotRecord] = {}
        order: list[str] = []
        for row in rows:
            snapshot_id = str(row.payload.get('snapshot_id') or '')
            key = snapshot_id or str(len(order))
            if key not in dedup:
                order.append(key)
            dedup[key] = row
        return tuple(dedup[key] for key in order if key in dedup)


__all__ = [
    "CANON_ECONOMIC_POLICY_SNAPSHOT_STORE",
    "EconomicPolicySnapshotRecord",
    "EconomicPolicySnapshotStore",
    "NoOpEconomicPolicySnapshotStore",
    "InMemoryEconomicPolicySnapshotStore",
    "JsonlEconomicPolicySnapshotStore",
]
