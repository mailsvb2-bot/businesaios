from __future__ import annotations

from dataclasses import dataclass

from config.app_settings import AppSettings
from infra.control_plane_boot_result import ControlPlaneBootResult
from infra.feature_flag_store import InMemoryFeatureFlagStore
from infra.feature_flags import FeatureFlags
from infra.kill_switches import KillSwitchRegistry
from infra.maintenance_mode import MaintenanceMode
from infra.release_fingerprint import build_release_fingerprint
from infra.rollout_policy import RolloutPolicy
from infra.runtime_guardrails import RuntimeGuardrails


@dataclass
class ControlPlaneBoot:
    app_settings: AppSettings

    def build(self) -> ControlPlaneBootResult:
        feature_flags = FeatureFlags(
            store=InMemoryFeatureFlagStore(),
        )
        kill_switches = KillSwitchRegistry()
        maintenance_mode = MaintenanceMode()
        rollout_policy = RolloutPolicy()
        release_fingerprint = build_release_fingerprint(
            version="v1",
            environment=self.app_settings.environment,
        )
        runtime_guardrails = RuntimeGuardrails(
            feature_flags=feature_flags,
            kill_switches=kill_switches,
            maintenance_mode=maintenance_mode,
        )

        return ControlPlaneBootResult(
            feature_flags=feature_flags,
            rollout_policy=rollout_policy,
            kill_switches=kill_switches,
            maintenance_mode=maintenance_mode,
            runtime_guardrails=runtime_guardrails,
            release_fingerprint=release_fingerprint,
        )
