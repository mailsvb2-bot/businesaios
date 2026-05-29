from __future__ import annotations

from typing import Any, Dict

from .base import Schema


class WorldStateSchemaV1(Schema):

    def validate(self, payload: dict[str, Any]) -> None:
        if "user" not in payload:
            raise ValueError("user missing")

    def normalize(self, payload: dict[str, Any]) -> dict[str, Any]:
        return payload

# Backward-compatible alias
WorldStateV1 = WorldStateSchemaV1
