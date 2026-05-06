from __future__ import annotations


def emit_survival_verdict(*, events, env, verdict) -> None:
    if events is None:
        return
    events.emit(
        event_type="survival_verdict",
        source="runtime.guard",
        user_id=str(getattr(env.decision, "user_id", "system")) if hasattr(env.decision, "user_id") else "system",
        decision_id=env.decision.decision_id,
        correlation_id=env.decision.correlation_id,
        payload={
            "mode": getattr(verdict.mode, "value", str(verdict.mode)),
            "reason": verdict.reason,
            "allow_execution": verdict.allow_execution,
            "trigger_rollback": bool(getattr(verdict, "trigger_rollback", False)),
            "trigger_safe_offers": bool(getattr(verdict, "trigger_safe_offers", False)),
        },
    )


def enforce_survival_gate(*, survival, events, env) -> None:
    if survival is None:
        return
    verdict = survival.evaluate()
    emit_survival_verdict(events=events, env=env, verdict=verdict)
    if not verdict.allow_execution:
        raise RuntimeError(f"SURVIVAL_BLOCK:{verdict.reason or 'blocked'}")
