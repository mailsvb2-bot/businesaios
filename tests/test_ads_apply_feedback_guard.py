from dataclasses import dataclass, field

from core.ads.apply.contract import AdsApplyRequest
from core.ads.apply.limits import AdsApplyLimits
from core.ads.apply_engine import AdsApplyEngine, AdsApplyEnv
from core.ads.apply_gate import AdsApplyState
from core.ads.hardening.kill_switch import AdsKillSwitch
from core.ads.hardening.rate_limiter import AdsRateLimiter
from core.api.idempotency import IdempotencyKey, MemoryIdempotencyStore
from core.governance.guards.feedback_loop_guard import GuardDecision


class DummyApplyPort:
    def __init__(self):
        self.called = False

    def perform_apply(self, tenant_id: str, plan):
        self.called = True
        return {"ok": True}


class DummyFeedbackGuard:
    def __init__(self, allowed: bool):
        self.allowed = allowed

    def check_planned_budget(self, *, tenant_id: str, planned_daily_budget_minor: int):
        if self.allowed:
            return GuardDecision(allowed=True)
        return GuardDecision(allowed=False, code="ADS_RUNAWAY_FEEDBACK_LOOP", message="blocked")


@dataclass(frozen=True)
class DummyCmd:
    platform: str = "meta"
    action: str = "set_budget"
    payload: dict = field(default_factory=lambda: {"daily_budget_minor": 1000})


@dataclass(frozen=True)
class DummyPlan:
    commands: list
    notes: str = ""


def _engine(allowed: bool):
    return AdsApplyEngine(
        apply_port=DummyApplyPort(),
        kill_switch=AdsKillSwitch(),
        rate_limiter=AdsRateLimiter(rate=10.0, burst=10),
        idempotency=MemoryIdempotencyStore(),
        env=AdsApplyEnv(hard_env_enabled=True, limits=AdsApplyLimits(max_daily_budget_minor=10_000, max_changes_per_day=10)),
        feedback_guard=DummyFeedbackGuard(allowed=allowed),
    )


def test_feedback_guard_blocks_apply_before_provider_call():
    engine = _engine(False)
    req = AdsApplyRequest(
        tenant_id="t1",
        user_id="u1",
        plan=DummyPlan(commands=[DummyCmd()]),
        idempotency=IdempotencyKey(tenant_id="t1", key="k1"),
        dry_run=False,
    )
    res = engine.execute(req=req, gate_state=AdsApplyState(enabled=True))
    assert res.status == "blocked"
    assert res.detail["error"] == "ADS_RUNAWAY_FEEDBACK_LOOP"
    assert res.audit_event["payload"]["status"] == "blocked"
