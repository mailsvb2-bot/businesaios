from __future__ import annotations

import asyncio
import sys
from types import SimpleNamespace

from core.marketing.async_runner import run_awaitable_sync
from runtime.boot import ads_apply_provider
from runtime.handlers.ai_ceo_plan import handle_ai_ceo_plan
from runtime.handlers.growth_propose import handle_growth_propose
from runtime.handlers.route_failure_support import best_effort_route_ids, normalized_tenant_id


class _Effects:
    def __init__(self):
        self.calls = []

    def send_message(self, **kwargs):
        self.calls.append(kwargs)
        return kwargs


def test_best_effort_route_ids_prefers_env_decision():
    env = SimpleNamespace(decision=SimpleNamespace(decision_id='d1', correlation_id='c1'))
    assert best_effort_route_ids(payload={'decision_id': 'd2', 'correlation_id': 'c2'}, env=env) == ('d1', 'c1')


def test_growth_propose_route_violation_keeps_env_ids_and_safe_text():
    fx = _Effects()
    env = SimpleNamespace(decision=SimpleNamespace(decision_id='d1', correlation_id='c1'))
    out = handle_growth_propose({'user_id': 'u1'}, fx, env, proposal_service=None, proposal_gateway=None)
    assert out['decision_id'] == 'd1'
    assert out['correlation_id'] == 'c1'
    assert 'route contract' in out['text'].lower()
    assert out['track_payload']['error'] == 'DecisionRouteViolation'


def test_ai_ceo_plan_error_does_not_leak_exception_text():
    class _BadPlanner:
        def build_plan(self, **kwargs):
            raise ValueError('secret details')

    fx = _Effects()
    env = SimpleNamespace(decision=SimpleNamespace(decision_id='d1', correlation_id='c1', issuer_id='businesaios-core', action='ai_ceo_plan@v1', tenant_id='t1'))
    out = handle_ai_ceo_plan({'user_id': 'u1', 'tenant_id': 't1', 'decision_id': 'd1', 'correlation_id': 'c1', 'issued_action': 'ai_ceo_plan@v1'}, fx, env, planner=_BadPlanner())
    assert 'secret details' not in out['text']
    assert out['track_payload']['error'] == 'ValueError'


def test_run_awaitable_sync_works_inside_running_loop():
    async def _inner():
        return run_awaitable_sync(asyncio.sleep(0, result=7))

    assert asyncio.run(_inner()) == 7


def test_ads_apply_provider_run_works_inside_running_loop():
    async def _inner():
        return ads_apply_provider._run(asyncio.sleep(0, result='ok'))

    assert asyncio.run(_inner()) == 'ok'


def test_normalized_tenant_id_rejects_placeholders():
    assert normalized_tenant_id('default') == ''
    assert normalized_tenant_id('legacy') == ''
    assert normalized_tenant_id('t1') == 't1'


def test_run_product_preflight_if_any_skips_placeholder_tenant(monkeypatch):
    from runtime.boot import system_builder_steps as mod

    fake_tenant_mod = SimpleNamespace(current_tenant_id=lambda: 'default')
    monkeypatch.setitem(sys.modules, 'core.tenancy.tenant', fake_tenant_mod)

    called = {'n': 0}

    def _fake_run_product_preflight(*, tenant_id: str):
        called['n'] += 1
        return SimpleNamespace(blocked=False, system='x')

    monkeypatch.setattr(mod, 'run_product_preflight', _fake_run_product_preflight)
    assert mod.run_product_preflight_if_any() is None
    assert called['n'] == 0


def test_resolve_autopilot_contract_does_not_inject_default_tenant(monkeypatch):
    import core.autopilot.resolver as resolver

    seen = {}

    def _fake_loader(*, tenant_id: str, ref: str = ''):
        seen['tenant_id'] = tenant_id
        seen['ref'] = ref
        return {'ok': True}

    monkeypatch.setattr(resolver, 'load_autopilot_contract_from_env', _fake_loader)
    missing_tenant_id = ''.join([])
    resolver.resolve_autopilot_contract(product={'autopilot_contract_ref': 'x'}, tenant_id=missing_tenant_id)
    assert seen['tenant_id'] == missing_tenant_id
    assert seen['ref'] == 'x'
