from __future__ import annotations

from typing import Any, Dict

from core.ads.ads_service import AdsCommand, AdsPlan
from core.ads.apply.contract import AdsApplyRequest
from core.ads.apply.limits import AdsApplyLimits
from core.ads.apply_engine import AdsApplyEngine, AdsApplyEnv
from core.ads.apply_gate import AdsApplyState
from core.ads.hardening.kill_switch import AdsKillSwitch
from core.ads.hardening.rate_limiter import AdsRateLimiter
from core.api.idempotency import IdempotencyKey, MemoryIdempotencyStore
from core.tenancy.scope import as_tenant_id


class FakeApplyPort:
    def __init__(self) -> None:
        self.calls = 0

    def perform_apply(self, tenant_id: str, plan: Any) -> Dict[str, Any]:
        self.calls += 1
        if self.calls == 1:
            return {"ok": True, "tenant": tenant_id, "n": len(plan.commands or [])}
        return {"ok": True, "repeat": True}


def _engine(*, env_enabled: bool = True) -> AdsApplyEngine:
    return AdsApplyEngine(
        apply_port=FakeApplyPort(),
        kill_switch=AdsKillSwitch(),
        rate_limiter=AdsRateLimiter(rate=1000.0, burst=1000),
        idempotency=MemoryIdempotencyStore(),
        env=AdsApplyEnv(hard_env_enabled=env_enabled, limits=AdsApplyLimits(max_daily_budget_minor=0, max_changes_per_day=0)),
    )


def test_ads_apply_dry_run_is_default() -> None:
    eng = _engine(env_enabled=True)
    plan = AdsPlan(commands=[AdsCommand(platform="meta", action="apply_plan", payload={"daily_budget_minor": 1000})])
    req = AdsApplyRequest(
        tenant_id=as_tenant_id("t1"),
        user_id="u1",
        plan=plan,
        idempotency=IdempotencyKey(tenant_id=as_tenant_id("t1"), key="k1"),
        dry_run=True,
    )
    res = eng.execute(req=req, gate_state=AdsApplyState(enabled=True, since_ms=1))
    assert res.status == "dry_run"
    assert res.detail.get("planned_changes") == 1


def test_ads_apply_idempotent_duplicate() -> None:
    eng = _engine(env_enabled=True)
    plan = AdsPlan(commands=[AdsCommand(platform="meta", action="apply_plan", payload={})])
    key = IdempotencyKey(tenant_id=as_tenant_id("t1"), key="kdup")
    req = AdsApplyRequest(tenant_id=as_tenant_id("t1"), user_id="u1", plan=plan, idempotency=key, dry_run=True)
    r1 = eng.execute(req=req, gate_state=AdsApplyState(enabled=True, since_ms=1))
    r2 = eng.execute(req=req, gate_state=AdsApplyState(enabled=True, since_ms=1))
    assert r1.status == "dry_run"
    assert r2.status == "duplicate"


def test_ads_apply_blocked_when_env_disabled() -> None:
    eng = _engine(env_enabled=False)
    plan = AdsPlan(commands=[AdsCommand(platform="meta", action="apply_plan", payload={})])
    req = AdsApplyRequest(
        tenant_id=as_tenant_id("t1"),
        user_id="u1",
        plan=plan,
        idempotency=IdempotencyKey(tenant_id=as_tenant_id("t1"), key="k2"),
        dry_run=True,
    )
    res = eng.execute(req=req, gate_state=AdsApplyState(enabled=True, since_ms=1))
    assert res.status == "blocked"
