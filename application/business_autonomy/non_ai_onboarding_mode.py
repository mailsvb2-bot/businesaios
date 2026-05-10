from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Mapping


class NonAiOperatingMode(str, Enum):
    LOW_AUTONOMY = "low_autonomy"
    POLICY_GUIDED = "policy_guided"
    SUPERVISED = "supervised"
    EXTERNAL_HUMAN_OWNED = "external_human_owned"
    CHANNEL_DRIVEN = "channel_driven"


@dataclass(frozen=True)
class NonAiModePolicy:
    mode: NonAiOperatingMode
    autonomy_tier: str
    requires_human_approval: bool
    requires_external_confirmation: bool
    effect_write_enabled: bool

    def to_metadata(self) -> dict[str, object]:
        return {
            "non_ai_mode": self.mode.value,
            "autonomy_tier": self.autonomy_tier,
            "requires_human_approval": self.requires_human_approval,
            "requires_external_confirmation": self.requires_external_confirmation,
            "effect_write_enabled": self.effect_write_enabled,
        }


class NonAiModeResolver:
    def resolve(self, *, metadata: Mapping[str, Any]) -> NonAiModePolicy:
        requested = str(metadata.get("non_ai_mode") or NonAiOperatingMode.SUPERVISED.value).strip().lower()
        try:
            mode = NonAiOperatingMode(requested)
        except ValueError as exc:
            raise ValueError(f"unsupported non_ai_mode: {requested}") from exc
        if mode is NonAiOperatingMode.LOW_AUTONOMY:
            return NonAiModePolicy(mode, "low_autonomy", True, False, False)
        if mode is NonAiOperatingMode.POLICY_GUIDED:
            return NonAiModePolicy(mode, "policy_guided", True, False, True)
        if mode is NonAiOperatingMode.EXTERNAL_HUMAN_OWNED:
            return NonAiModePolicy(mode, "external_human_owned", True, True, False)
        if mode is NonAiOperatingMode.CHANNEL_DRIVEN:
            return NonAiModePolicy(mode, "channel_driven", True, False, False)
        return NonAiModePolicy(mode, "supervised", True, False, True)


__all__ = ["NonAiModePolicy", "NonAiModeResolver", "NonAiOperatingMode"]
