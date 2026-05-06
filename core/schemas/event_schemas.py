from __future__ import annotations

from typing import Dict, Any
from .base import Schema


class UserTransitEventV1(Schema):
    """User transit/location check-in (platform-agnostic)."""
    REQUIRED = {"user_id", "timestamp", "station"}

    def validate(self, payload: Dict[str, Any]) -> None:
        missing = self.REQUIRED - payload.keys()
        if missing:
            raise ValueError(f"Missing fields: {missing}")

    def normalize(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "user_id": str(payload["user_id"]),
            "ts": int(payload["timestamp"]),
            "station": payload["station"],
        }
