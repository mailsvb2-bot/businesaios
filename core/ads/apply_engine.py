"""Production-hard Ads Apply Engine.

Responsibilities:
- Enforce kill-switch + rate limits
- Enforce ads apply gate (user + env) + soft limits
- Provide strict idempotency (Idempotency-Key)
- Support dry-run (preview) by default
- Best-effort rollback on failure (if provider returns undo hints)
- Emit an audit event payload (caller appends to event store)

This module is orchestration but stays small by delegating primitives to
core.ads.apply.* modules.
"""

from __future__ import annotations

from dataclasses import dataclass

from core.ads.apply.contract import AdsApplyRequest, AdsApplyResult
from core.ads.apply.limits import AdsApplyLimits
from core.ads.apply_engine_execution import build_dry_run_result, perform_apply_flow
from core.ads.apply_engine_helpers import AdsApplyPort
from core.ads.apply_engine_prechecks import (
    build_duplicate_result,
    check_kill_switch,
    check_rate_limit,
    evaluate_gate_and_feedback,
)
from core.ads.apply_gate import AdsApplyState
from core.ads.hardening.kill_switch import AdsKillSwitch
from core.ads.hardening.rate_limiter import AdsRateLimiter
from core.api.idempotency import IdempotencyStore
from core.governance.guards.feedback_loop_guard import FeedbackLoopGuard

__all__ = ["AdsApplyEngine", "AdsApplyEnv", "AdsApplyPort"]

@dataclass(frozen=True)
class AdsApplyEnv:
    hard_env_enabled: bool
    limits: AdsApplyLimits


class AdsApplyEngine:
    def __init__(
        self,
        *,
        apply_port: AdsApplyPort,
        kill_switch: AdsKillSwitch,
        rate_limiter: AdsRateLimiter,
        idempotency: IdempotencyStore,
        env: AdsApplyEnv,
        feedback_guard: FeedbackLoopGuard | None = None,
    ) -> None:
        self._apply_port = apply_port
        self._kill = kill_switch
        self._rl = rate_limiter
        self._idem = idempotency
        self._env = env
        self._feedback_guard = feedback_guard

    def execute(
        self,
        *,
        req: AdsApplyRequest,
        gate_state: AdsApplyState,
        ttl_ms: int = 6 * 60 * 60 * 1000,
    ) -> AdsApplyResult:
        idem_norm = req.idempotency.normalized()

        ks = self._kill.state
        blocked = check_kill_switch(enabled=bool(ks.enabled), reason=ks.reason, req=req, idem_norm=idem_norm)
        if blocked is not None:
            return blocked

        try:
            self._rl.assert_allowed(str(req.tenant_id))
            rate_allowed = True
        except Exception:
            rate_allowed = False
        blocked = check_rate_limit(allowed=rate_allowed, req=req, idem_norm=idem_norm)
        if blocked is not None:
            return blocked

        if not self._idem.try_begin(key=req.idempotency, ttl_ms=int(ttl_ms)):
            prev = self._idem.get(key=req.idempotency)
            return build_duplicate_result(previous=(prev.result if prev else None), req=req, idem_norm=idem_norm)

        gate_result, planned_budget_minor, planned_changes, failure_code = evaluate_gate_and_feedback(
            req=req,
            idem_norm=idem_norm,
            gate_state=gate_state,
            hard_env_enabled=bool(self._env.hard_env_enabled),
            max_daily_budget_minor=int(self._env.limits.max_daily_budget_minor),
            max_changes_per_day=int(self._env.limits.max_changes_per_day),
            feedback_guard=self._feedback_guard,
        )
        if gate_result is not None:
            self._idem.mark_failed(key=req.idempotency, reason=str(failure_code or 'ADS_APPLY_BLOCKED'))
            return gate_result

        if bool(req.dry_run):
            result, response = build_dry_run_result(
                req=req,
                idem_norm=idem_norm,
                planned_budget_minor=int(planned_budget_minor),
                planned_changes=int(planned_changes),
            )
            self._idem.mark_done(key=req.idempotency, result=result)
            return response

        mark, response = perform_apply_flow(
            apply_port=self._apply_port,
            req=req,
            idem_norm=idem_norm,
            planned_changes=int(planned_changes),
        )
        if mark == 'done':
            self._idem.mark_done(key=req.idempotency, result=response.detail)
        else:
            self._idem.mark_failed(key=req.idempotency, reason='APPLY_FAILED')
        return response

