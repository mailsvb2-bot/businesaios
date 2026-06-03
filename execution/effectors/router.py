from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from collections.abc import Mapping

from execution.effectors import build_effector
from execution.effectors.result import EffectorResult


CANON_EFFECTOR_ROUTER = True


@dataclass
class EffectorRouter:
    def execute(self, *, action_type: str, action: Mapping[str, Any]) -> EffectorResult:
        effector = build_effector(action_type)
        return effector.execute(action)


__all__ = ["CANON_EFFECTOR_ROUTER", "EffectorRouter"]
