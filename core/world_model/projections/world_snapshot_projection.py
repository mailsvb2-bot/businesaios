from __future__ import annotations

from dataclasses import asdict

from core.world_model.types import WorldSnapshot


class WorldSnapshotProjection:
    def project(self, *, snapshot: WorldSnapshot) -> dict:
        return asdict(snapshot)
