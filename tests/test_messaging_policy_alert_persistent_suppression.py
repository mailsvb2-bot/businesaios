from runtime.messaging_policy_alert_dedup.record import AlertNotificationDedupRecord
from runtime.messaging_policy_alert_dedup.suppression_service import AlertNotificationSuppressionService
from runtime.messaging_policy_alert_dedup_persistent.store import PersistentAlertNotificationDedupStore


class _GW:
    def __init__(self):
        self.items = {}

    def get_value(self, *, tenant_id: str, key: str):
        return self.items.get((tenant_id, key))

    def set_value(self, *, tenant_id: str, key: str, value: dict):
        self.items[(tenant_id, key)] = dict(value)


def test_persistent_suppression_respects_saved_state(monkeypatch):
    import runtime.messaging_policy_alert_dedup.suppression_service as mod

    gw = _GW()
    store = PersistentAlertNotificationDedupStore(settings_gateway=gw, tenant_id="t1")
    store.put(AlertNotificationDedupRecord(dedup_key="t1|ceo|telegram|a1|u1", sent_at_epoch_s=100))

    monkeypatch.setattr(mod, "now_epoch_s", lambda: 130)

    svc = AlertNotificationSuppressionService(store=store, cooldown_s=60)
    _, decision = svc.issue(
        tenant_id="t1",
        recipient_user_id="ceo",
        channel="telegram",
        alert_code="a1",
        affected_user_id="u1",
    )

    assert decision.should_send is False
    assert decision.reason == "cooldown_active"
