from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from core.behavior.operator_catalogs.operator_catalog_resolver import OperatorCatalogKey, OperatorCatalogResolver
from core.behavior.operator_policy_catalogs.resolver import OperatorPolicyCatalogResolver
from core.behavior.operators.operator_context_resolver import resolve_operator_runtime_context
from core.offers.offer_catalog_resolver import OfferCatalogKey, OfferCatalogResolver
from core.retention.decision_adapter_support import try_build_offer_step
from core.retention.decision_steps import render_offer_step
from runtime.messaging_policy_alert_dedup_persistent.store import PersistentAlertNotificationDedupStore
from runtime.messaging_policy_alert_subscriptions.subscription_record import AlertSubscriptionRecord
from runtime.telegram_message_factory import resolve_tenant_id


class _CatalogRegistry:
    def __init__(self):
        self.calls = []

    def get(self, catalog_id):
        self.calls.append(catalog_id)
        if catalog_id == 'default:organization_platform:prod':
            return SimpleNamespace(catalog_id=catalog_id)
        raise KeyError(catalog_id)


class _OfferRegistry:
    def __init__(self):
        self.calls = []

    def get(self, catalog_id):
        self.calls.append(catalog_id)
        if catalog_id == 'default:organization_platform:prod':
            return {'id': catalog_id}
        raise KeyError(catalog_id)


class _SettingsGateway:
    def __init__(self):
        self.calls = []

    def get_value(self, **kwargs):
        self.calls.append(('get', kwargs))
        return None

    def set_value(self, **kwargs):
        self.calls.append(('set', kwargs))


class _OfferEngine:
    def should_show_offer(self, **kwargs):
        self.kwargs = kwargs
        return True, {'reason': 'ok'}

    def render_offer(self, **kwargs):
        self.kwargs = kwargs
        return SimpleNamespace(text='txt', variant='a', meta={}, price_rub=123, offer_id=kwargs['offer_id'])


def test_operator_runtime_context_normalizes_placeholder_tenant():
    ctx = resolve_operator_runtime_context({'tenant_id': 'default', 'operator_catalog_ref': ''})
    assert ctx.tenant_id is None
    assert ctx.operator_catalog_ref == 'default'


def test_operator_catalog_resolver_skips_placeholder_tenant_branch():
    reg = _CatalogRegistry()
    cat = OperatorCatalogResolver(catalogs=reg).resolve(
        key=OperatorCatalogKey(tenant_id='default', product_id='organization_platform', environment='prod'),
        fallback_catalog_id='default',
    )
    assert cat.catalog_id == 'default:organization_platform:prod'
    assert reg.calls[0] == 'default:organization_platform:prod'
    assert 'default:default:prod' not in reg.calls


def test_operator_policy_catalog_resolver_uses_default_product_without_placeholder_tenant(tmp_path: Path):
    root = tmp_path / 'products' / 'operator_policy_catalogs'
    root.mkdir(parents=True)
    (root / 'default_organization_platform_prod.yaml').write_text('version: 1\ndefaults:\n  allow: [purchase_success]\n', encoding='utf-8')
    cat = OperatorPolicyCatalogResolver(root_dir=str(root)).resolve(
        catalog_ref=None,
        tenant_id='default',
        product_id='organization_platform',
        env='prod',
    )
    assert cat.name == 'default:organization_platform:prod'


def test_offer_catalog_resolver_skips_placeholder_tenant_branch():
    reg = _OfferRegistry()
    cat = OfferCatalogResolver(catalogs=reg).resolve(
        key=OfferCatalogKey(tenant_id='default', product_id='organization_platform', environment='prod')
    )
    assert cat['id'] == 'default:organization_platform:prod'
    assert reg.calls[0] == 'default:organization_platform:prod'


def test_retention_offer_step_suppresses_when_no_real_tenant():
    missing_tenant_id = ''.join([])
    decision = SimpleNamespace(
        suppressed=False,
        offer_arm='offer_a',
        offer_price_rub=123,
        debug={},
        tenant_id=missing_tenant_id,
        day_key='day:1',
        day_index=1,
    )
    state = SimpleNamespace(tenant_id='default', price_constraints=None)
    step, dbg = try_build_offer_step(
        decision=decision,
        state=state,
        offer_engine=_OfferEngine(),
        cooldown_store=None,
        user_id='u1',
    )
    assert step is None
    assert dbg['constraints']['reason'] == 'missing_tenant_id'


def test_render_offer_step_prefers_decision_tenant_over_placeholder_state_tenant():
    engine = _OfferEngine()
    decision = SimpleNamespace(tenant_id='tenant-1', offer_arm='offer_a', offer_price_rub=123, day_key='day:1', day_index=1)
    state = SimpleNamespace(tenant_id='default', telegram_update=None, locale='ru', user_locale='ru', features={})
    step, _ = render_offer_step(offer_engine=engine, state=state, decision=decision, user_id='u1', max_band=None)
    assert engine.kwargs['tenant_id'] == 'tenant-1'
    assert step['tenant_id'] == 'tenant-1'


def test_subscription_record_normalizes_placeholder_tenant_to_unknown():
    rec = AlertSubscriptionRecord(tenant_id='default', recipient_user_id='u1', channel='telegram', min_level='warn')
    assert rec.tenant_id == 'unknown_tenant'


def test_persistent_dedup_store_uses_normalized_unknown_tenant():
    gateway = _SettingsGateway()
    store = PersistentAlertNotificationDedupStore(settings_gateway=gateway, tenant_id='default')
    store.get(dedup_key='k1')
    kind, payload = gateway.calls[0]
    assert kind == 'get'
    assert payload['tenant_id'] == 'unknown_tenant'


def test_message_factory_uses_unknown_tenant_when_no_real_tenant_present():
    assert resolve_tenant_id(tenant_id='default', track_payload={'tenant_id': 'legacy'}) == 'unknown_tenant'
