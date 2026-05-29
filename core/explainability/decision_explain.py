from __future__ import annotations

from typing import Any, Dict

from core.decision.ai_decision_trace import DecisionTrace


def explain(trace: DecisionTrace, *, max_steps: int = 8) -> dict[str, Any]:
    """Return a structured explanation.

    No LLM calls. Pure deterministic formatting.
    """
    steps = []
    for s in (trace.steps or [])[: max(1, int(max_steps))]:
        steps.append(
            {
                "name": s.name,
                "summary": _summarize_step(s.input, s.output),
                "duration_ms": int(s.duration_ms or 0),
            }
        )

    return {
        "trace_id": trace.trace_id,
        "decision_id": trace.decision_id,
        "issued_at_ms": trace.issued_at_ms,
        "meta": dict(trace.meta or {}),
        "steps": steps,
    }


def _summarize_step(inp: dict[str, Any], out: dict[str, Any]) -> str:
    # Keep explainability compact and safe (no secrets, no PII beyond user_id which isn't here).
    # Callers decide what to show to the end-user.
    parts = []
    if "policy_id" in out:
        parts.append(f"policy={out.get('policy_id')}")
    if "rollout_group" in out:
        parts.append(f"group={out.get('rollout_group')}")
    if "allowed_price_band" in out:
        parts.append(f"price_band={out.get('allowed_price_band')}")
    if "action" in out:
        parts.append(f"action={out.get('action')}")
    return "; ".join(parts) if parts else "ok"
