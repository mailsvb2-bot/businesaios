from __future__ import annotations

from runtime.execution.executor_state import build_executor_runtime_infra_from_runtime_infra
from runtime.runtime_infra import RuntimeInfra


def test_build_executor_runtime_infra_from_runtime_infra_preserves_canonical_fields():
    infra = RuntimeInfra(
        ledger="ledger",
        snapshot_store="snap",
        outbox="outbox",
        payment_outbox="payments",
        settings_gateway="settings",
        messaging_policy_event_store="mp-store",
        messaging_policy_read_service="mp-reader",
    )

    executor_infra = build_executor_runtime_infra_from_runtime_infra(
        runtime_infra=infra,
        delivery_state="delivery",
        telegram_outbound_queue="queue",
    )

    assert executor_infra.ledger == "ledger"
    assert executor_infra.snapshot_store == "snap"
    assert executor_infra.outbox == "outbox"
    assert executor_infra.payment_outbox == "payments"
    assert executor_infra.settings_gateway == "settings"
    assert executor_infra.messaging_policy_event_store == "mp-store"
    assert executor_infra.messaging_policy_read_service == "mp-reader"
    assert executor_infra.delivery_state == "delivery"
    assert executor_infra.telegram_outbound_queue == "queue"
