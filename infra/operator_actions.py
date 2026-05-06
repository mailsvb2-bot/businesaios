from __future__ import annotations

from dataclasses import dataclass

from infra.audit_log_service import AuditLogService
from infra.feature_flags import FeatureFlags
from infra.kill_switches import KillSwitchRegistry
from infra.maintenance_mode import MaintenanceMode


@dataclass(frozen=True)
class OperatorActionsService:
    feature_flags: FeatureFlags
    kill_switches: KillSwitchRegistry
    maintenance_mode: MaintenanceMode
    audit_log: AuditLogService

    def enable_feature_flag(self, *, actor: str, name: str) -> None:
        self.feature_flags.enable(name)
        self.audit_log.record(
            event_name="feature_flag_enabled",
            actor=actor,
            category="operator_action",
            payload={"name": name},
        )

    def disable_feature_flag(self, *, actor: str, name: str) -> None:
        self.feature_flags.disable(name)
        self.audit_log.record(
            event_name="feature_flag_disabled",
            actor=actor,
            category="operator_action",
            payload={"name": name},
        )

    def trip_kill_switch(self, *, actor: str, name: str) -> None:
        self.kill_switches.trip(name)
        self.audit_log.record(
            event_name="kill_switch_tripped",
            actor=actor,
            category="operator_action",
            payload={"name": name},
        )

    def reset_kill_switch(self, *, actor: str, name: str) -> None:
        self.kill_switches.reset(name)
        self.audit_log.record(
            event_name="kill_switch_reset",
            actor=actor,
            category="operator_action",
            payload={"name": name},
        )

    def enable_maintenance_mode(
        self,
        *,
        actor: str,
        reason: str | None = None,
    ) -> None:
        self.maintenance_mode.enable(reason=reason)
        self.audit_log.record(
            event_name="maintenance_mode_enabled",
            actor=actor,
            category="operator_action",
            payload={"reason": reason},
        )

    def disable_maintenance_mode(self, *, actor: str) -> None:
        self.maintenance_mode.disable()
        self.audit_log.record(
            event_name="maintenance_mode_disabled",
            actor=actor,
            category="operator_action",
            payload={},
        )
