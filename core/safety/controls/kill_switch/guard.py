from __future__ import annotations

from ..action_context import SafetyActionContext
from ..control_result import ControlDecision, ControlStatus
from .registry import InMemoryKillSwitchRegistry


class KillSwitchGuard:
    control_name = "kill_switch"

    def __init__(self, registry: InMemoryKillSwitchRegistry):
        self._registry = registry

    def evaluate(self, ctx: SafetyActionContext) -> ControlDecision:
        matched = [snapshot for snapshot in self._registry.matching(ctx.action) if snapshot.active]
        if matched:
            return ControlDecision(
                control=self.control_name,
                status=ControlStatus.BLOCK,
                reason="kill_switch_active",
                details={"matched_prefixes": [s.action_prefix for s in matched]},
            )
        return ControlDecision(control=self.control_name, status=ControlStatus.ALLOW, reason="kill_switch_clear")
