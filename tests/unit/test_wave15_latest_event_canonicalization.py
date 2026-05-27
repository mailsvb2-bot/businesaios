from __future__ import annotations

from core.entitlements.read_model import compute_entitlements
from core.events.read_call import call_latest_event
from core.growth.ads.rl.contracts import AdsRLOptSpec
from core.growth.ads.rl.observer import observe_tick_once
from core.payments.read_model import latest_payment_status
from core.read_model.cache import watermark_for
from core.users.read_model import selected_product, selected_tariff, user_settings
from runtime.platform.event_store.memory_event_store import MemoryEventStore


class _LatestEventLegacy:
    def latest_event(self, *, tenant_id='default', user_id=None, event_type=None):
        return {
            'tenant_id': tenant_id,
            'user_id': user_id,
            'event_type': event_type,
            'timestamp_ms': 123,
            'payload': {'full_access': True, 'status': 'succeeded', 'tariff': 'pro', 'key': 'city', 'value': 'Amsterdam'},
        }


class _LatestEventModern:
    def latest_event(self, *, tenant_id='default', user_id=None, event_types=None):
        return {
            'tenant_id': tenant_id,
            'user_id': user_id,
            'event_type': event_types[0] if event_types else None,
            'timestamp_ms': 456,
            'payload': {'status': 'succeeded'},
        }


class _LatestEventBroken:
    def latest_event(self, *, tenant_id='default', user_id=None, event_types=None):
        raise TypeError('internal latest bug must not be masked')


class _UserStoreLegacy:
    def latest_event(self, *, tenant_id='default', user_id=None, event_type=None):
        payload = {
            'tariff_selected': {'tariff': 'premium', 'days': 30},
            'product_selected@v1': {'product_id': 'p1'},
        }[event_type]
        return {'tenant_id': tenant_id, 'user_id': user_id, 'event_type': event_type, 'timestamp_ms': 1000, 'payload': payload}

    def latest_events(self, *, tenant_id='default', user_id=None, event_type=None, limit=200):
        return [
            {'tenant_id': tenant_id, 'user_id': user_id, 'event_type': event_type, 'timestamp_ms': 1, 'payload': {'key': 'city', 'value': 'Paris'}},
            {'tenant_id': tenant_id, 'user_id': user_id, 'event_type': event_type, 'timestamp_ms': 2, 'payload': {'key': 'city', 'value': 'Berlin'}},
            {'tenant_id': tenant_id, 'user_id': user_id, 'event_type': event_type, 'timestamp_ms': 3, 'payload': {'key': 'lang', 'value': 'ru'}},
        ]

    def iter_events(self, *, tenant_id='default', start_ms=0, end_ms=None, user_id=None, event_type=None):
        return []


class _EntitlementStoreLegacy:
    def latest_event(self, *, tenant_id='default', user_id=None, event_type=None):
        return {'tenant_id': tenant_id, 'user_id': user_id, 'event_type': event_type, 'timestamp_ms': 321, 'payload': {'full_access': True}}

    def iter_events(self, *, tenant_id='default', start_ms=0, end_ms=None, event_type=None, user_id=None):
        return []


class _PaymentStoreLegacy:
    def latest_event(self, *, tenant_id='default', user_id=None, event_type=None):
        return {'tenant_id': tenant_id, 'user_id': user_id, 'event_type': 'payment_succeeded', 'timestamp_ms': 654, 'payload': {'invoice_id': 'inv1'}}

    def iter_events(self, *, tenant_id='default', start_ms=0, end_ms=None, event_type=None, user_id=None):
        return []


class DummyRL:
    def __init__(self):
        self.calls = []

    def observe(self, *, tenant_id: str, user_id, spec, policy_id: str, action, meta):
        self.calls.append({'tenant_id': tenant_id, 'spec': spec, 'policy_id': policy_id, 'action': action, 'meta': meta})
        return {'status': 'ok'}


def test_call_latest_event_supports_modern_and_legacy_signatures() -> None:
    modern = call_latest_event(latest_fn=_LatestEventModern().latest_event, tenant_id='t1', user_id='u1', event_types=('x',), legacy_event_type='x')
    legacy = call_latest_event(latest_fn=_LatestEventLegacy().latest_event, tenant_id='t1', user_id='u1', event_types=('x',), legacy_event_type='x')
    assert modern['event_type'] == 'x'
    assert legacy['event_type'] == 'x'


def test_call_latest_event_does_not_mask_internal_type_errors() -> None:
    try:
        call_latest_event(latest_fn=_LatestEventBroken().latest_event, tenant_id='t1', user_id='u1', event_types=('x',), legacy_event_type='x')
    except TypeError as exc:
        assert 'internal latest bug must not be masked' in str(exc)
    else:  # pragma: no cover
        raise AssertionError('expected TypeError')


def test_read_models_use_canonical_latest_event_calls() -> None:
    user_store = _UserStoreLegacy()
    assert selected_tariff(user_store, tenant_id='t1', user_id='u1')['tariff'] == 'premium'
    assert selected_product(user_store, user_id='u1')['product_id'] == 'p1'
    settings = user_settings(user_store, tenant_id='t1', user_id='u1')
    assert settings['city'] == 'Paris'
    assert settings['lang'] == 'ru'

    entitlements = compute_entitlements(event_store=_EntitlementStoreLegacy(), tenant_id='t1', user_id='u1')
    assert entitlements['full_access'] is True

    payment = latest_payment_status(event_store=_PaymentStoreLegacy(), tenant_id='t1', user_id='u1')
    assert payment['status'] == 'succeeded'
    assert payment['invoice_id'] == 'inv1'


def test_watermark_for_uses_signature_safe_latest_event() -> None:
    assert watermark_for(_LatestEventLegacy(), tenant_id='t1', user_id='u1', event_types=('x',)) == 123
    assert watermark_for(_LatestEventModern(), tenant_id='t1', user_id='u1', event_types=('x',)) == 456


def test_ads_rl_observer_checkpoint_reads_via_canonical_latest_event() -> None:
    es = MemoryEventStore()
    rl = DummyRL()
    tid = 't1'
    import time
    now = int(time.time() * 1000)

    spec = AdsRLOptSpec(
        platform='meta',
        campaign_id='c1',
        daily_budgets=[10.0],
        bid_caps=[0.5],
        cpa_targets=[3.0],
        creatives=['cr1'],
        audiences=['a1'],
        objectives=['sales'],
    )

    es.append_event({
        'tenant_id': tid,
        'user_id': 'u1',
        'source': 'ads_rl',
        'event_type': 'ads_rl_suggested@v1',
        'timestamp_ms': now - 10_000,
        'payload': {
            'policy_id': 'p1',
            'campaign_id': 'c1',
            'platform': 'meta',
            'action_key': 'k',
            'action': {'campaign_id': 'c1', 'daily_budget': 12.0},
            'meta': {'spec': spec.to_json()},
        },
    })
    es.append_event({
        'event_id': 'e_import_1',
        'tenant_id': tid,
        'user_id': '',
        'source': 'ads_import',
        'event_type': 'ads_metrics_imported',
        'timestamp_ms': now - 1_000,
        'payload': {'ref': {'platform': 'meta', 'object_type': 'campaign', 'object_id': 'c1'}, 'metrics': {'spend': 1.0}},
    })

    first = observe_tick_once(tenant_id=tid, event_store=es, rl_service=rl, max_import_events=50)
    second = observe_tick_once(tenant_id=tid, event_store=es, rl_service=rl, max_import_events=50)
    assert first.processed == 1
    assert second.status == 'no_new_events'
