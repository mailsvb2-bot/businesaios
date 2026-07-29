from __future__ import annotations

from datetime import datetime, timezone

from application.decisioning.authenticated_command import AuthenticatedDecisionCommandBinding
from core.ai.decision_contracts import SignedDecision
from runtime.security.keyring import Keyring


def build_authenticated_command_binding() -> AuthenticatedDecisionCommandBinding:
    keyring = Keyring()
    keyring.add_key("test-api-command", "test-api-command-secret-32-bytes-long", active=True)
    return AuthenticatedDecisionCommandBinding(
        keyring=keyring,
        issuer="tests.api.authenticated_command_fixture",
        ttl_seconds=300,
        clock=lambda: datetime(2026, 7, 29, 10, 0, tzinfo=timezone.utc),
        envelope_type=SignedDecision,
    )
