from __future__ import annotations

import json
from dataclasses import asdict

from core.world_model.types import WorldSnapshot


class JsonReadyWorldSnapshotSerializer:
    def to_dict(self, snapshot: WorldSnapshot) -> dict:
        payload = asdict(snapshot)
        if snapshot.freshness is not None:
            payload["freshness"]["per_reader"] = {k: v.value for k, v in snapshot.freshness.per_reader.items()}
            payload["freshness"]["worst_status"] = snapshot.freshness.worst_status.value
        payload["status"] = snapshot.status.value
        return payload

    def to_canonical_json(self, snapshot: WorldSnapshot) -> str:
        return json.dumps(self.to_dict(snapshot), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
