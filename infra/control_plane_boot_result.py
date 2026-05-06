from __future__ import annotations

from dataclasses import dataclass

from infra.feature_flags import FeatureFlags
from infra.kill_switches import KillSwitchRegistry
from infra.maintenance_mode import MaintenanceMode
from infra.release_fingerprint import ReleaseFingerprint
from infra.rollout_policy import RolloutPolicy
from infra.runtime_guardrails import RuntimeGuardrails


@dataclass(frozen=True)
class ControlPlaneBootResult:
    feature_flags: FeatureFlags
    rollout_policy: RolloutPolicy
    kill_switches: KillSwitchRegistry
    maintenance_mode: MaintenanceMode
    runtime_guardrails: RuntimeGuardrails
    release_fingerprint: ReleaseFingerprint
