from dataclasses import dataclass

from reliability.outbox_store import InMemoryOutboxStore, OutboxState
from runtime.execution.executor_commit import (
    claim_or_skip,
    enqueue_once,
    get_delivery_info,
    has_pending,
    mark_delivered,
)


@dataclass
class _Decision:
    decision_id: str = "dec-1"
    correlation_id: str = "corr-1"
    action: str = "send_email"
    payload: dict | None = None


def test_executor_commit_supports_reliability_outbox_store() -> None:
    outbox = InMemoryOutboxStore()
    decision = _Decision(payload={"tenant_id": "tenant-a", "to": "a@example.com"})
    enqueue_once(outbox, decision=decision)

    row = outbox.get(tenant_id="tenant-a", message_id="dec-1")
    assert row is not None
    assert row.topic == "runtime.effect.send_email"
    assert row.effect_kind == "runtime_effect"

    assert claim_or_skip(outbox, decision_id="dec-1", tenant_id="tenant-a", owner_id="runtime-executor")
    mark_delivered(outbox, decision_id="dec-1", tenant_id="tenant-a", owner_id="runtime-executor", backend_name="runtime_executor", external_id="dec-1")

    updated = outbox.get(tenant_id="tenant-a", message_id="dec-1")
    assert updated is not None
    assert updated.state is OutboxState.DELIVERED
    assert updated.backend_name == "runtime_executor"
    assert has_pending(outbox, decision_id="dec-1", tenant_id="tenant-a") is False

    info = get_delivery_info(outbox, decision_id="dec-1", tenant_id="tenant-a")
    assert info is not None
    assert info["backend_name"] == "runtime_executor"
    assert info["state"] == "delivered"
