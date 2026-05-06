from runtime.messaging_policy_alert_dedup.inmemory_store import InMemoryAlertNotificationDedupStore
from runtime.messaging_policy_alert_dedup.record import AlertNotificationDedupRecord
from runtime.messaging_policy_alert_dedup.suppression_service import AlertNotificationSuppressionService


def test_suppression_service_blocks_during_cooldown(monkeypatch):
    import runtime.messaging_policy_alert_dedup.suppression_service as mod
    store = InMemoryAlertNotificationDedupStore()
    store.put(AlertNotificationDedupRecord(dedup_key="t1|ceo|telegram|a1|u1", sent_at_epoch_s=100))
    monkeypatch.setattr(mod, "now_epoch_s", lambda: 120)
    svc = AlertNotificationSuppressionService(store=store, cooldown_s=60)
    _, decision = svc.issue(tenant_id="t1", recipient_user_id="ceo", channel="telegram", alert_code="a1", affected_user_id="u1")
    assert decision.should_send is False
    assert decision.reason == "cooldown_active"
