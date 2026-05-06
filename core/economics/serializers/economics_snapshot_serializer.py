from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from ..types import EconomicsSnapshot


@dataclass
class EconomicsSnapshotSerializer:
    def serialize(self, snapshot: EconomicsSnapshot) -> dict[str, Any]:
        payload = asdict(snapshot)
        payload["snapshot_id"] = snapshot.snapshot_id.value
        payload["built_at"] = snapshot.built_at.isoformat()
        return payload
