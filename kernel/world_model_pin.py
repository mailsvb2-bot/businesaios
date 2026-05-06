from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional


@dataclass(frozen=True)
class WorldModelPin:
    world_model: Optional[str]
    world_model_kind: Optional[str]
    pricing_world_model: Optional[str]
    pricing_world_model_version: Optional[str]
    pricing_world_model_hash: Optional[str]
    pricing_world_state_hash: Optional[str]
    world_model_source: Optional[str]

    @classmethod
    def from_payload(cls, payload: Dict[str, Any] | None) -> "WorldModelPin":
        payload = dict(payload or {})
        return cls(
            world_model=_as_str_or_none(payload.get("world_model")),
            world_model_kind=_as_str_or_none(payload.get("world_model_kind")),
            pricing_world_model=_as_str_or_none(payload.get("pricing_world_model")),
            pricing_world_model_version=_as_str_or_none(payload.get("pricing_world_model_version")),
            pricing_world_model_hash=_as_str_or_none(payload.get("pricing_world_model_hash")),
            pricing_world_state_hash=_as_str_or_none(payload.get("pricing_world_state_hash")),
            world_model_source=_as_str_or_none(payload.get("world_model_source")),
        )

    def to_dict(self) -> Dict[str, Any]:
        out: Dict[str, Any] = {}
        if self.world_model is not None:
            out["world_model"] = self.world_model
        if self.world_model_kind is not None:
            out["world_model_kind"] = self.world_model_kind
        if self.pricing_world_model is not None:
            out["pricing_world_model"] = self.pricing_world_model
        if self.pricing_world_model_version is not None:
            out["pricing_world_model_version"] = self.pricing_world_model_version
        if self.pricing_world_model_hash is not None:
            out["pricing_world_model_hash"] = self.pricing_world_model_hash
        if self.pricing_world_state_hash is not None:
            out["pricing_world_state_hash"] = self.pricing_world_state_hash
        if self.world_model_source is not None:
            out["world_model_source"] = self.world_model_source
        return out


@dataclass(frozen=True)
class WorldModelPinCheckResult:
    ok: bool
    strict: bool
    reason: str
    pinned: Dict[str, Any]
    current: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ok": bool(self.ok),
            "strict": bool(self.strict),
            "reason": str(self.reason),
            "pinned": dict(self.pinned),
            "current": dict(self.current),
        }


def _as_str_or_none(value: Any) -> Optional[str]:
    if value is None:
        return None
    s = str(value).strip()
    return s or None
