from __future__ import annotations

from dataclasses import asdict

from core.world_model.types import DemandState


class DemandStateProjection:
    def project(self, *, state: DemandState) -> dict:
        return asdict(state)
