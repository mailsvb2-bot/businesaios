from runtime.messaging_policy_alert_dedup.record import AlertNotificationDedupRecord
from runtime.messaging_policy_alert_dedup_persistent.tenant_store_factory import TenantScopedDedupStoreFactory
from runtime.messaging_policy_alert_dedup_persistent.tenant_suppression_service import (
    TenantAwareAlertNotificationSuppressionService,
)


class _GW:
    def __init__(self):
        self.items = {}

    def get_value(self, *, tenant_id: str, key: str):
        return self.items.get((tenant_id, key))

    def set_value(self, *, tenant_id: str, key: str, value: dict):
        self.items[(tenant_id, key)] = dict(value)


def test_tenant_scoped_store_factory_isolates_state_between_tenants():
    gw = _GW()
    factory = TenantScopedDedupStoreFactory(settings_gateway=gw)
    t1 = factory.for_tenant(tenant_id='tenant-1')
    t2 = factory.for_tenant(tenant_id='tenant-2')
    t1.put(AlertNotificationDedupRecord(dedup_key='k', sent_at_epoch_s=100))
    assert t1.get(dedup_key='k') is not None
    assert t2.get(dedup_key='k') is None


def test_tenant_aware_suppression_uses_tenant_scoped_state(monkeypatch):
    import runtime.messaging_policy_alert_dedup_persistent.tenant_suppression_service as mod
    gw = _GW()
    factory = TenantScopedDedupStoreFactory(settings_gateway=gw)
    tenant_1_store = factory.for_tenant(tenant_id='tenant-1')
    tenant_1_store.put(AlertNotificationDedupRecord(dedup_key='tenant-1|ceo|telegram|a1|u1', sent_at_epoch_s=100))
    monkeypatch.setattr(mod, 'now_epoch_s', lambda: 120)
    svc = TenantAwareAlertNotificationSuppressionService(store_factory=factory, cooldown_s=60)
    _, d1 = svc.evaluate(tenant_id='tenant-1', recipient_user_id='ceo', channel='telegram', alert_code='a1', affected_user_id='u1')
    _, d2 = svc.evaluate(tenant_id='tenant-2', recipient_user_id='ceo', channel='telegram', alert_code='a1', affected_user_id='u1')
    assert d1.should_send is False
    assert d2.should_send is True
