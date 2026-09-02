from __future__ import annotations

from contextlib import ExitStack
from threading import Barrier, Lock, Thread

from runtime.messaging_policy_alert_dedup_persistent.tenant_mark_sent_service import (
    TenantAwareAlertNotificationMarkSentService,
)
from runtime.messaging_policy_alert_dedup_persistent.tenant_notifier import (
    TenantAwareDedupingMessagingPolicyAlertNotifier,
)
from runtime.messaging_policy_alert_dedup_persistent.tenant_store_factory import TenantScopedDedupStoreFactory
from runtime.messaging_policy_alert_dedup_persistent.tenant_suppression_service import (
    TenantAwareAlertNotificationSuppressionService,
)
from runtime.messaging_policy_alert_subscriptions.notification_item import AlertNotificationItem
from runtime.messaging_policy_alert_subscriptions.notification_plan import AlertNotificationPlan
from runtime.messaging_policy_alert_subscriptions.notifier_result import AlertNotifierResult
from runtime.platform.event_store.sqlite_event_store import SqliteEventStore
from runtime.settings.event_store_gateway import build_event_store_settings_gateway


class _BarrierSuppression:
    def __init__(self, *, delegate, barrier: Barrier):
        self._delegate = delegate
        self._barrier = barrier

    def evaluate(self, **kwargs):
        result = self._delegate.evaluate(**kwargs)
        self._barrier.wait(timeout=5)
        return result


class _ApprovalNotifier:
    def __init__(self):
        self.calls = 0
        self._lock = Lock()

    def notify(self, **_kwargs):
        with self._lock:
            self.calls += 1
            approval_id = f"ap-{self.calls}"
        return AlertNotifierResult(notifications_total=1, notifications_sent=0, pending_approval_ids=(approval_id,))


def _notifier(*, gateway, barrier: Barrier, base_notifier):
    factory = TenantScopedDedupStoreFactory(settings_gateway=gateway)
    suppression = _BarrierSuppression(delegate=TenantAwareAlertNotificationSuppressionService(store_factory=factory, cooldown_s=60), barrier=barrier)
    mark = TenantAwareAlertNotificationMarkSentService(store_factory=factory)
    return TenantAwareDedupingMessagingPolicyAlertNotifier(base_notifier=base_notifier, suppression_service=suppression, mark_sent_service=mark)


def test_two_persistent_alert_workers_atomically_claim_before_creating_approval(tmp_path):
    db_path = str(tmp_path / "events.sqlite3")
    barrier = Barrier(2)
    base = _ApprovalNotifier()
    plan = AlertNotificationPlan(items=(AlertNotificationItem(tenant_id="tenant-a", business_id="biz-a", recipient_user_id="C1", channel="slack", text="alert", alert_code="a1", alert_level="critical", affected_user_id="u1"),))
    results = []
    with ExitStack() as stack:
        stores = [stack.enter_context(SqliteEventStore(db_path)) for _ in range(2)]
        notifiers = [_notifier(gateway=build_event_store_settings_gateway(event_store=store), barrier=barrier, base_notifier=base) for store in stores]

        def _run(index: int):
            results.append(notifiers[index].notify(plan=plan, effects=None, decision_id=f"d-{index}", correlation_id=f"c-{index}"))

        threads = [Thread(target=_run, args=(index,)) for index in range(2)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=10)
            assert not thread.is_alive()

    assert base.calls == 1
    assert sum(item.notifications_pending for item in results) == 1
    assert sum(item.notifications_suppressed for item in results) == 1


class _IndexFailingGateway:
    def __init__(self):
        self.items = {}

    def get_value(self, *, tenant_id: str, key: str):
        return self.items.get((tenant_id, key))

    def set_value(self, *, tenant_id: str, key: str, value):
        if "__approval__" in key:
            raise RuntimeError("simulated approval-index failure")
        self.items[(tenant_id, key)] = dict(value)

    def compare_and_set_value(self, *, tenant_id: str, key: str, expected, value) -> bool:
        slot = (tenant_id, key)
        if self.items.get(slot) != expected:
            return False
        self.items[slot] = dict(value)
        return True


def test_new_pending_lifecycle_does_not_depend_on_separate_approval_index_write():
    factory = TenantScopedDedupStoreFactory(settings_gateway=_IndexFailingGateway())
    mark = TenantAwareAlertNotificationMarkSentService(store_factory=factory)
    dedup_key = "tenant-a|biz-a|ceo|slack|a1|u1"
    assert mark.reserve(tenant_id="tenant-a", dedup_key=dedup_key, expected_record=None, reservation_id="res-1") is True
    assert mark.mark_pending(tenant_id="tenant-a", dedup_key=dedup_key, approval_id="ap-1", reservation_id="res-1") is True
    assert mark.finalize_approval(tenant_id="tenant-a", approval_id="ap-1", dedup_key=dedup_key, reservation_id="res-1", delivered=False) is True
    assert factory.for_tenant(tenant_id="tenant-a").get(dedup_key=dedup_key) is None
    assert mark.reserve(tenant_id="tenant-a", dedup_key=dedup_key, expected_record=None, reservation_id="res-2") is True
