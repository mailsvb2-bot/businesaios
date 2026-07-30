from __future__ import annotations

from application.decisioning.authenticated_command import AuthenticatedDecisionCommandBinding
from core.security.keyring import Keyring


def build_authenticated_command_binding() -> AuthenticatedDecisionCommandBinding:
    return AuthenticatedDecisionCommandBinding(
        keyring=Keyring(
            {"api-test-key": {"secret": b"api-test-signing-secret", "revoked": False}},
            "api-test-key",
        ),
        clock_ms=lambda: 1_700_000_000_000,
        ttl_ms=60_000,
    )


__all__ = ["build_authenticated_command_binding"]
