from __future__ import annotations

import json
from typing import Any

from core.economics.types import EconomicState
from core.observability.silent import swallow
from core.reward.reward_details import build_reward_details


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
        if not (isinstance(econ, dict) and "retention_prob" in econ and ("revenue" in econ or "cost" in econ)):
            return None
        state = EconomicState.from_world_economy(econ)
        try:
            if hasattr(engine._brain, "components"):
                ltv, spend, reward = engine._brain.components(state)  # type: ignore[attr-defined]
                details = build_reward_details(reward=float(reward), ltv=float(ltv), spend=float(spend), source="governed_reward_components")
                engine._last_details = {"ltv": details.ltv, "spend": details.spend, "reward": details.reward, "source": details.source}
                return float(reward)
        except Exception:
            swallow(__name__, 'core/reward/observe_flow.py')
        return float(engine._brain.step(state))
    except Exception:
        return None


def shape_fallback_reward(*, engine: Any, env: Any, execution_output: Any, reward: float) -> float:
    r = float(reward)
    try:
        if str(env.decision.action).startswith("capture_payment"):
            engine._last_details = {"spend": float(abs(r) / max(1e-9, engine._money_scale))}
    except Exception:
        swallow(__name__, 'core/reward/observe_flow.py')

    try:
        act = str(env.decision.action)
        if act == "grant_access@v1":
            r += 10.0
        if act == "reconcile_payments@v1" and isinstance(execution_output, dict) and str(execution_output.get("status")) in {"succeeded", "payment_succeeded"}:
            r += 20.0
    except Exception:
        swallow(__name__, 'core/reward/observe_flow.py')

    if r > engine._max_abs_reward:
        r = engine._max_abs_reward
    if r < -engine._max_abs_reward:
        r = -engine._max_abs_reward
    return float(r)
