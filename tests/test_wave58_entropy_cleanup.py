from __future__ import annotations

import pytest

from core.ai.decision_runtime import validate_and_gate_action
from core.behavior.operator_catalogs.resolver import resolve_operator_context
from core.offers.catalog_resolution import resolve_catalog
from runtime.telegram_message_factory import resolve_tenant_id
from runtime.handlers.ads_autopilot.result_text import render_gate_error_text
from runtime.handlers_messaging import _resolve_tenant_id
from runtime.autopilot_feedback_guard import AutopilotFeedbackGuardViolation
from runtime.self_driving_scheduler import tick_once


class _Events:
    def __init__(self):
        self.calls = []

    def emit(self, **kwargs):
        self.calls.append(kwargs)


class _Schemas:
    def validate(self, action, payload):
        return 1


class _Selector:
    def select(self, state):
        return None


class _Trace:
    def try_add_step(self, **kwargs):
        return None


class _Out:
    action = 'send_message@v1'
    payload = {'user_id': 'u1'}


def test_decision_runtime_emits_error_class_not_raw_message(monkeypatch):
    import application.decision_runtime.runtime as mod

    def _boom(**kwargs):
        raise ValueError('super secret details')

    monkeypatch.setattr(mod, 'gate_action_or_raise', _boom)
    events = _Events()
    with pytest.raises(RuntimeError):
        validate_and_gate_action(schemas=_Schemas(), state=type('S', (), {'product_metadata': {'tenant_id': 't1'}, 'tenant_id': 't1'})(), out=_Out(), user_id='u1', events=events, trace=_Trace())
    assert events.calls
    payload = events.calls[0]['payload']
    assert payload['error'] == 'ValueError'
    assert 'secret' not in str(payload)


def test_resolve_operator_context_does_not_invent_default_tenant():
    ctx = resolve_operator_context(product={'id': 'p1'}, tenant_id='default')
    assert ctx['tenant_id'] == ''


def test_offer_catalog_resolution_skips_placeholder_tenant_resolver():
    class _Catalogs:
        def __init__(self):
            self.calls = []
        def get(self, name):
            self.calls.append(name)
            if name == 'offer_catalog_legacy@v1':
                return {'id': name}
            raise KeyError(name)
    catalogs = _Catalogs()
    out = resolve_catalog(catalogs=catalogs, product={'id': 'p1'}, tenant_id='default', context=None)
    assert out == {'id': 'offer_catalog_legacy@v1'}


def test_message_tenant_resolution_prefers_real_track_payload_tenant():
    assert resolve_tenant_id(tenant_id='default', track_payload={'tenant_id': 't1'}) == 't1'


def test_handlers_messaging_tenant_resolution_uses_normalized_sources():
    env = type('Env', (), {'tenant_id': 'default', 'default_tenant_id': 't2', 'decision': None})()
    assert _resolve_tenant_id({'track_payload': {'tenant_id': 'legacy'}}, env) == 't2'


def test_render_gate_error_text_hides_raw_exception_text():
    text = render_gate_error_text(RuntimeError('raw details'))
    assert 'raw details' not in text
    assert 'RuntimeError' in text


def test_self_driving_scheduler_status_hides_raw_feedback_error(monkeypatch):
    class _Guard:
        def validate_action_vs_evaluation(self, **kwargs):
            raise AutopilotFeedbackGuardViolation('private reason')
    monkeypatch.setattr('runtime.self_driving_scheduler._FEEDBACK_GUARD', _Guard())
    learning = type('L', (), {'maybe_propose_deployment': lambda self: {'kind': 'deploy'}})()
    res = tick_once(learning_system=learning, decision_core=None, executor=None)
    assert res.status == 'feedback_guard:AutopilotFeedbackGuardViolation'
