from __future__ import annotations

from dataclasses import dataclass, field

from infra.feature_flags import FeatureFlags
from infra.kill_switches import KillSwitchRegistry
from infra.maintenance_mode import MaintenanceMode


@dataclass(frozen=True)
class GuardrailDecision:
    allowed: bool
    reasons: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class RuntimeGuardrails:
    feature_flags: FeatureFlags
    kill_switches: KillSwitchRegistry
    maintenance_mode: MaintenanceMode

    def evaluate(
        self,
        *,
        operation_name: str,
        required_feature_flag: str | None = None,
        kill_switch_name: str | None = None,
        allow_during_maintenance: bool = False,
    ) -> GuardrailDecision:
        reasons: list[str] = []

        if self.maintenance_mode.is_enabled() and not allow_during_maintenance:
            reasons.append("maintenance_mode_enabled")

        if required_feature_flag is not None:
            if not self.feature_flags.is_enabled(required_feature_flag):
                reasons.append(f"feature_flag_disabled:{required_feature_flag}")

        if kill_switch_name is not None:
            if self.kill_switches.is_tripped(kill_switch_name):
                reasons.append(f"kill_switch_tripped:{kill_switch_name}")

        return GuardrailDecision(
            allowed=not reasons,
            reasons=tuple(reasons),
        )
