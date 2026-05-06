from __future__ import annotations

import hashlib
import json

from ..action_catalog import ActionSafetyCatalog, build_default_action_catalog
from ..action_context import SafetyActionContext
from ..action_identity import stable_payload
from ..control_result import ControlDecision, ControlStatus
from .store import RunawayLoopStore


class RunawayLoopGuard:
    control_name = "runaway_loop_guard"

    def __init__(self, store: RunawayLoopStore, repetition_threshold: int = 3, catalog: ActionSafetyCatalog | None = None):
        self._store = store
        self._threshold = int(repetition_threshold)
        self._catalog = catalog or build_default_action_catalog()

    def evaluate(self, ctx: SafetyActionContext) -> ControlDecision:
        spec = self._catalog.resolve(ctx.action)
        if spec is None or not bool(spec.high_impact):
            return ControlDecision(
                control=self.control_name,
                status=ControlStatus.ALLOW,
                reason="runaway_guard_not_applicable",
            )
        fingerprint = hashlib.sha256(
            json.dumps({"action": ctx.action, "payload": stable_payload(dict(ctx.payload))}, sort_keys=True, default=str).encode("utf-8")
        ).hexdigest()
        recent = self._store.append(ctx.tenant_id, fingerprint)
        repeats = sum(1 for item in recent if item == fingerprint)
        if repeats >= self._threshold:
            return ControlDecision(
                control=self.control_name,
                status=ControlStatus.BLOCK,
                reason="runaway_loop_detected",
                details={"repeats": repeats, "window": len(recent)},
            )
        return ControlDecision(control=self.control_name, status=ControlStatus.ALLOW, reason="runaway_loop_clear")
