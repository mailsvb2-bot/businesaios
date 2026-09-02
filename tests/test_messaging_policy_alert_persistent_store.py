from runtime.messaging_policy_alert_dedup.record import AlertNotificationDedupRecord
from runtime.messaging_policy_alert_dedup_persistent.store import PersistentAlertNotificationDedupStore


class _GW:
    def __init__(self):
        self.items = {}

    def get_value(self, *, tenant_id: str, key: str):
        return self.items.get((tenant_id, key))

    def set_value(self, *, tenant_id: str, key: str, value: dict):
        self.items[(tenant_id, key)] = dict(value)


def test_persistent_store_put_and_get():
    gw = _GW()
    store = PersistentAlertNotificationDedupStore(settings_gateway=gw, tenant_id="t1")

    store.put(AlertNotificationDedupRecord(dedup_key="k1", sent_at_epoch_s=123))
    rec = store.get(dedup_key="k1")

    assert rec is not None
    assert rec.dedup_key == "k1"
    assert rec.sent_at_epoch_s == 123


def test_persistent_store_indexes_pending_approval_and_round_trips_state():
    gw = _GW()
    store = PersistentAlertNotificationDedupStore(settings_gateway=gw, tenant_id="t1")
    store.put(AlertNotificationDedupRecord(dedup_key="k-pending", sent_at_epoch_s=0, pending_approval_id="ap-1"))
    store.bind_pending_approval(approval_id="ap-1", dedup_key="k-pending")
    rec = store.get(dedup_key="k-pending")
    assert rec is not None and rec.is_pending and rec.pending_approval_id == "ap-1"
    assert store.dedup_key_for_approval(approval_id="ap-1") == "k-pending"
