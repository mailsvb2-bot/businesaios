from __future__ import annotations

import pytest

from application.decisioning.authenticated_command import AuthenticatedDecisionCommandBinding
from core.security.keyring import Keyring
from entrypoints.api.request_context import RequestContext
from kernel.decisioning.route_contract import DecisionRouteViolation, EXPECTED_ISSUER_ID


def _binding() -> AuthenticatedDecisionCommandBinding:
    return AuthenticatedDecisionCommandBinding(
        keyring=Keyring({"k1": {"secret": b"test-secret", "revoked": False}}, "k1"),
        clock_ms=lambda: 1_700_000_000_000,
        ttl_ms=60_000,
    )


def _context() -> RequestContext:
    return RequestContext(
        request_id="request-1",
        correlation_id="correlation-1",
        tenant_id="tenant-a",
        actor_id="actor-a",
        subject="subject-a",
        metadata={"authenticated_principal": True},
    )


def test_authenticated_command_binding_emits_verified_envelope_without_selection() -> None:
    envelope = _binding().signed_envelope(
        action="pricing.publish_offer",
        payload={"offer_id": "offer-1", "amount": 199},
        request_context=_context(),
        action_id="action-1",
    )

    envelope.verify()
    decision = envelope.decision
    assert decision.issuer_id == EXPECTED_ISSUER_ID
    assert decision.decision_id == "api-command:tenant-a:action-1"
    assert decision.correlation_id == "correlation-1"
    assert decision.action == "pricing.publish_offer"
    assert decision.payload["tenant_id"] == "tenant-a"
    assert decision.payload["actor_id"] == "actor-a"
    assert decision.payload["command_source"] == "authenticated_api"
    assert decision.issued_at_ms == 1_700_000_000_000
    assert decision.expires_at_ms == 1_700_000_060_000


def test_authenticated_command_binding_is_deterministic_for_same_identity() -> None:
    first = _binding().signed_envelope(
        action="pricing.publish_offer",
        payload={"offer_id": "offer-1", "amount": 199},
        request_context=_context(),
        action_id="action-1",
    )
    second = _binding().signed_envelope(
        action="pricing.publish_offer",
        payload={"amount": 199, "offer_id": "offer-1"},
        request_context=_context(),
        action_id="action-1",
    )

    assert second.decision.decision_id == first.decision.decision_id
    assert second.decision.state_hash == first.decision.state_hash
    assert second.payload_hash == first.payload_hash
    assert second.signature == first.signature


def test_authenticated_command_binding_fails_closed_without_principal_proof() -> None:
    context = RequestContext(
        request_id="request-1",
        tenant_id="tenant-a",
        actor_id="actor-a",
    )
    with pytest.raises(DecisionRouteViolation, match="principal proof"):
        _binding().signed_envelope(
            action="pricing.publish_offer",
            payload={},
            request_context=context,
            action_id="action-1",
        )
