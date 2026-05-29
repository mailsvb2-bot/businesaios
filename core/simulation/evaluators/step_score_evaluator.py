from __future__ import annotations

from typing import Any, Dict

from config.scoring_behavior_policy import DEFAULT_ACTION_RANKING_POLICY

from ..contracts import SimScore


def evaluate_step_score(*, action: str, payload: dict[str, Any], snapshot: dict[str, Any]) -> SimScore:
    p = dict(payload or {})
    exp = float(p.get("expected_profit_delta_minor") or 0.0)
    uplift = float(p.get("uplift") or 0.0)
    risk = float(p.get("risk_penalty") or 0.0)

    base = (exp * 1.0) + (uplift * 100.0) - (risk * 1000.0)
    a = str(action or "")
    if a.startswith("noop"):
        base -= 1.0
    if "apply" in a:
        base -= 5.0
    if "request" in a or "plan" in a:
        base += 2.0
    if "one_click" in a:
        base += 3.0

    conf = 0.2
    if exp or uplift:
        conf = 0.6
    if risk:
        conf = min(conf, 0.5)

    return SimScore(
        score=float(base),
        confidence=float(conf),
        debug={"exp": exp, "uplift": uplift, "risk": risk, "snapshot": dict(snapshot or {})},
    )
