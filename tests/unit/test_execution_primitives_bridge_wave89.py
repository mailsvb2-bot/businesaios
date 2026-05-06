from execution.action_idempotency import ActionIdempotency
from execution.primitives import SetIdempotencyGate, StatusRetryPolicy
from routing_execution.lead_delivery_idempotency import LeadDeliveryIdempotency
from routing_execution.lead_delivery_retry import LeadDeliveryRetry


def test_set_idempotency_gate_claims_once() -> None:
    gate = SetIdempotencyGate()
    assert gate.claim('k1') is True
    assert gate.claim('k1') is False


def test_action_idempotency_uses_shared_seen_set() -> None:
    idem = ActionIdempotency()
    assert idem.allow('a1') is True
    assert idem.seen == {'a1'}
    assert idem.allow('a1') is False


def test_lead_delivery_idempotency_claims_composite_key_once() -> None:
    idem = LeadDeliveryIdempotency()
    assert idem.claim('r1', 'b1') is True
    assert idem.claim('r1', 'b1') is False
    assert idem.claim('r1', 'b2') is True


def test_status_retry_policy_matches_delivery_retry_semantics() -> None:
    policy = StatusRetryPolicy(terminal_status='ok', max_attempts=3)
    assert policy.should_retry(attempt=1, status='error') is True
    assert policy.should_retry(attempt=2, status='queued') is True
    assert policy.should_retry(attempt=3, status='error') is False
    assert policy.should_retry(attempt=1, status='ok') is False


def test_lead_delivery_retry_uses_status_retry_policy() -> None:
    retry = LeadDeliveryRetry(policy=StatusRetryPolicy(terminal_status='ok', max_attempts=3))
    seen = []

    def operation():
        seen.append(len(seen) + 1)
        return {'status': 'error' if len(seen) < 3 else 'ok', 'detail': 'x'}

    result = retry.run(operation)
    assert result['status'] == 'ok'
    assert seen == [1, 2, 3]
