from __future__ import annotations

from dataclasses import dataclass

from governance.kill_switch_registry import KillSwitchRegistry


CANON_GOVERNANCE_EMERGENCY_STOP_GUARD = True


@dataclass(frozen=True)
class EmergencyStopVerdict:
    allowed: bool
    reason: str
    blocking_scope: str | None = None
    blocking_scope_id: str | None = None


class EmergencyStopGuard:
    def __init__(self, *, registry: KillSwitchRegistry) -> None:
        self._registry = registry

    def evaluate(
        self,
        *,
        tenant_id: str,
        action_name: str,
        action_category: str | None,
    ) -> EmergencyStopVerdict:
        blocker = self._registry.find_blocker(
            tenant_id=tenant_id,
            action_name=action_name,
            action_category=action_category,
        )
        if blocker is None:
            return EmergencyStopVerdict(
                allowed=True,
                reason="allowed",
                blocking_scope=None,
                blocking_scope_id=None,
            )
        return EmergencyStopVerdict(
            allowed=False,
            reason=blocker.reason,
            blocking_scope=blocker.scope,
            blocking_scope_id=blocker.scope_id,
        )

    def require_allowed(
        self,
        *,
        tenant_id: str,
        action_name: str,
        action_category: str | None,
    ) -> None:
        verdict = self.evaluate(
            tenant_id=tenant_id,
            action_name=action_name,
            action_category=action_category,
        )
        if not verdict.allowed:
            raise RuntimeError(f"emergency_stop_active:{verdict.reason}")


__all__ = [
    "CANON_GOVERNANCE_EMERGENCY_STOP_GUARD",
    "EmergencyStopGuard",
    "EmergencyStopVerdict",
]
