from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class PolicyReturn:
    action: str
    payload: Mapping[str, Any]


class PolicyReturnValidator:
    def __init__(self, allowed_actions: set[str]) -> None:
        self._allowed = allowed_actions

    def assert_allowed(self, pr: PolicyReturn) -> None:
        if pr.action not in self._allowed:
            raise ValueError(f"Policy returned unregistered action: {pr.action}")
