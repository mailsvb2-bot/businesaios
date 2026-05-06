from __future__ import annotations

from dataclasses import dataclass, field

from infra.feature_flags import FeatureFlags
from infra.kill_switches import KillSwitchRegistry
from infra.maintenance_mode import MaintenanceMode


@dataclass(frozen=True)
class PolicySnapshot:
    name: str
    feature_flags: dict[str, bool] = field(default_factory=dict)
    kill_switches: dict[str, bool] = field(default_factory=dict)
    maintenance_mode_enabled: bool = False
    maintenance_reason: str | None = None


def build_policy_snapshot(
    *,
    name: str,
    feature_flags: FeatureFlags,
    kill_switches: KillSwitchRegistry,
    maintenance_mode: MaintenanceMode,
) -> PolicySnapshot:
    return PolicySnapshot(
        name=name,
        feature_flags=feature_flags.store.snapshot(),
        kill_switches=kill_switches.snapshot(),
        maintenance_mode_enabled=maintenance_mode.is_enabled(),
        maintenance_reason=maintenance_mode.reason(),
    )
