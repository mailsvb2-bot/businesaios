from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CanaryMeta:
    policy_version: str | None = None
    rollout_group: str | None = None
    canary: bool = False
