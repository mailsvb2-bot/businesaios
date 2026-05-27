from core.admin.read_models.pricing import pricing_change_requests
from core.admin.read_models.traffic import users_today
from core.retention.decision_adapter import RetentionDecisionAdapter
from core.retention.engine import RetentionEngine
from runtime.boot.web.messaging_policy_alert_subscription_service import (
    build_messaging_policy_alert_subscription_service,
)


class _Store:
    def __init__(self):
        self.calls = []

    def iter_events(self, *, tenant_id, start_ms=0, end_ms=None, event_type=None):
        self.calls.append({"tenant_id": tenant_id, "start_ms": start_ms, "end_ms": end_ms, "event_type": event_type})
        return iter([])


class _SettingsGateway:
    def __init__(self):
        self.calls = []

    def get_value(self, *, tenant_id, key):
        self.calls.append(("get", tenant_id, key))
        return None

    def set_value(self, *, tenant_id, key, value):
        self.calls.append(("set", tenant_id, key, value))


def test_admin_read_models_preserve_existing_global_scope_behavior():
    store = _Store()
    assert users_today(store, tenant_id="default") == 0
    pricing_change_requests(store, tenant_id="legacy")
    assert store.calls[0]["tenant_id"] == "default"
    assert store.calls[-1]["tenant_id"] == "legacy"


def test_retention_engine_normalizes_placeholder_tenant_to_unknown():
    engine = RetentionEngine(_Store(), tenant_id="default")
    assert engine.tenant_id == "unknown_tenant"
    assert engine.decide_offer(tenant_id="legacy", user_id="u1", context={}) is None


def test_retention_adapter_uses_canonical_unknown_tenant():
    adapter = RetentionDecisionAdapter(event_store=_Store(), tenant_id="default")
    assert adapter._engine.tenant_id == "unknown_tenant"


def test_messaging_policy_subscription_boot_uses_normalized_unknown_tenant():
    gateway = _SettingsGateway()
    bundle = build_messaging_policy_alert_subscription_service(alert_service=object(), settings_gateway=gateway, tenant_id="default")
    notifier = bundle["notifier_stack"]["notifier"]
    # force a read through the persistent dedup store
    notifier._suppression_service._store.get(dedup_key="x")
    assert gateway.calls[0][1] == "unknown_tenant"
