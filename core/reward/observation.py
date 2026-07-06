from __future__ import annotations

import json
from typing import Any

from core.economics.types import EconomicState
from core.observability.silent import swallow
from core.reward.delayed import eligible as delayed_eligible


def reward_observation_allowed(*, env: Any, now_ms: int) -> bool:
    try:
        return bool(delayed_eligible(event_time_ms=int(env.decision.issued_at_ms), now_ms=int(now_ms)))
    except Exception:
        return False


def observe_governed_reward(*, engine: Any, env: Any) -> float | None:
    if engine._snapshots is None or engine._brain is None:
        return None
    try:
        snap = engine._snapshots.get(str(env.decision.snapshot_id))
        if not snap:
            return None
        data = json.loads(snap.decode("utf-8"))
        econ = data.get("economy") if isinstance(data, dict) else None
        if isinstance(econ, dict) and "predicted_ltv" in econ:
            try:
                engine._last_details = {"ltv": float(econ.get("predicted_ltv"))}
            except Exception:
                engine._last_details = None
        if isinstance(econ, dict) and "retention_prob" in econ and ("revenue" in econ or "cost" in econ):
            state = EconomicState.from_world_economy(econ)
            try:
                if hasattr(engine._brain, "components"):
                    ltv, spend, reward = engine._brain.components(state)
                    engine._last_details = {"ltv": float(ltv), "spend": float(spend), "reward": float(reward)}
                    return float(reward)
            except Exception:
                swallow(__name__, 'core/reward/observation.py')
            return float(engine._brain.step(state))
    except Exception:
        return None
    return None


def finalize_reward(*, engine: Any, env: Any, execution_output: Any, reward: float) -> float:
    r = float(reward)
    try:
        if str(env.decision.action).startswith("capture_payment"):
            engine._last_details = {"spend": float(abs(r) / max(1e-9, engine._money_scale))}
    except Exception:
        swallow(__name__, 'core/reward/observation.py')
    try:
        act = str(env.decision.action)
        if act == "grant_access@v1":
            r += 10.0
        if act == "reconcile_payments@v1" and isinstance(execution_output, dict) and str(execution_output.get("status")) in {"succeeded", "payment_succeeded"}:
            r += 20.0
    except Exception:
        swallow(__name__, 'core/reward/observation.py')
    if r > engine._max_abs_reward:
        r = engine._max_abs_reward
    if r < -engine._max_abs_reward:
        r = -engine._max_abs_reward
    return float(r)
