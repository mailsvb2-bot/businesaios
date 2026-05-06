from __future__ import annotations

from dataclasses import asdict

from core.world_model.types import CustomerState


class CustomerStateProjection:
    def project(self, *, state: CustomerState) -> dict:
        return asdict(state)
