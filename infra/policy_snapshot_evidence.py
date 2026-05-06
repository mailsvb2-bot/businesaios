from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class PolicySnapshotEvidence:
    snapshot_name: str
    feature_flags: dict[str, bool] = field(default_factory=dict)
    kill_switches: dict[str, bool] = field(default_factory=dict)
    maintenance_mode_enabled: bool = False
    maintenance_reason: str | None = None
