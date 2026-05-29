"""Reward engine.

Maps executed decisions to scalar reward used for learning.

Governance:
  Prefer governed economic reward computed from the canonical WorldState snapshot.
  This keeps the loop closed WITHOUT moving business logic into runtime handlers.

Fallback:
  If economy features are missing, fall back to a safe monetary baseline.
"""

from __future__ import annotations

from typing import Any, Optional

from core.actions.proof_registry import ACTION_PROOF_EVENT
from core.ai.snapshot_store import SnapshotStore
from core.economics.brain import EconomicBrain
from core.observability.silent import swallow
from core.reward.delayed import eligible as _delayed_eligible
from core.reward.observe_flow import observe_governed_reward, shape_fallback_reward


class RewardEngine:
    def __init__(
        self,
        *,
        snapshot_store: SnapshotStore | None = None,
        economic_brain: EconomicBrain | None = None,
        event_log=None,
        money_scale: float = 0.01,
        max_abs_reward: float = 100.0,
    ):
        self._snapshots = snapshot_store
        self._brain = economic_brain
        self._events = event_log
        self._money_scale = float(money_scale)
        self._max_abs_reward = float(max_abs_reward)
        self._last_details: dict | None = None

    def _has_proof(self, *, decision_id: str, action: str) -> bool:
        """Reward is forbidden without a *valid* proof event (anti-gaming).

        IMPORTANT:
        - Mere existence of an event is not enough.
        - Proof must indicate success and must not be a stubbed integration.
        """
        expected_event = ACTION_PROOF_EVENT.get(str(action))
        if not expected_event:
            return False
        if self._events is None:
            return False

        # Preferred: structured access to proof events.
        get_events = getattr(self._events, "get_events", None)
        if callable(get_events):
            evs = list(get_events(str(decision_id), str(expected_event)))
        else:
            # Backward-compatible fallback.
            if not hasattr(self._events, "has_event"):
                return False
            return bool(self._events.has_event(str(decision_id), str(expected_event)))

        for ev in evs:
            payload = (ev.get("payload") if isinstance(ev, dict) else None) or {}
            ok = payload.get("ok")
            if ok is not True:
                continue
            meta = payload.get("meta") if isinstance(payload, dict) else None
            if isinstance(meta, dict) and str(meta.get("mode", "")) == "stub":
                continue
            return True
        return False


    def _fallback_money_reward(self, env, execution_output: Any) -> float:
        action = str(env.decision.action)
        payload = env.decision.payload or {}

        if action.startswith("capture_payment") or action.startswith("payment_capture"):
            amount = None
            if isinstance(payload, dict):
                amount = payload.get("amount")
            if amount is None and isinstance(execution_output, dict):
                amount = execution_output.get("amount")
            if amount is None:
                return 0.0
            return float(amount) * self._money_scale

        return 0.0


    def last_details(self) -> dict | None:
        """Return details from the last observe() call, if any."""
        return self._last_details

    def observe(self, env, execution_output) -> float:
        # Delayed reward: avoid instant gaming signals.
        try:
            import time as _time
            if not _delayed_eligible(event_time_ms=int(env.decision.issued_at_ms), now_ms=int(_time.time() * 1000)):
                return 0.0
        except Exception:
            # Never break runtime.
            return 0.0

        # 0) Anti-gaming: reward is forbidden without proof.
        if not self._has_proof(decision_id=str(env.decision.decision_id), action=str(env.decision.action)):
            return 0.0

        # 1) Governed reward from canonical snapshot (preferred)
        governed = observe_governed_reward(engine=self, env=env)
        if governed is not None:
            return float(governed)

        # 2) Safe baseline + bounded shaping
        base_reward = float(self._fallback_money_reward(env, execution_output))
        return shape_fallback_reward(
            engine=self,
            env=env,
            execution_output=execution_output,
            reward=base_reward,
        )
