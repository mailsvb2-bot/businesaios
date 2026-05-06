from __future__ import annotations

from typing import Dict, Any
from .base import Schema


class WorldStateSchemaV1(Schema):

    def validate(self, payload: Dict[str, Any]) -> None:
        if "user" not in payload:
            raise ValueError("user missing")

    def normalize(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return payload

# Backward-compatible alias
WorldStateV1 = WorldStateSchemaV1
