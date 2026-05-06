from runtime.messaging_policy_alert_dedup.inmemory_store import InMemoryAlertNotificationDedupStore
from runtime.messaging_policy_alert_dedup.record import AlertNotificationDedupRecord


def test_inmemory_store_put_and_get():
    store = InMemoryAlertNotificationDedupStore()
    store.put(AlertNotificationDedupRecord(dedup_key="k1", sent_at_epoch_s=100))
    rec = store.get(dedup_key="k1")
    assert rec is not None
    assert rec.sent_at_epoch_s == 100
