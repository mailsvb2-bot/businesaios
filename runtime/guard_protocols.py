"""Guard protocols and reference DTO. RuntimeGuard lives in runtime.guard."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from runtime.decision import DecisionEnvelope
from runtime.platform.config.env_flags import env_int

SUPPORTED_ENVELOPE_VERSION = 1
MAX_REPLAY_MS = env_int("MAX_REPLAY_MS", 10 * 60 * 1000, lo=1)


class DecisionExpired(RuntimeError):
    pass


@dataclass(frozen=True)
class DecisionEnvelopeRef:
    """Reference-mode DTO for guarded side-effects (tests/adapters)."""

    decision_id: str
    action: str
    payload_hash: str
    signature: str


class DecisionLedger(Protocol):
    """Ledger contract for the runtime law."""

    def try_mark_executed(self, env: DecisionEnvelope) -> bool: ...
    def is_executed(self, decision_id: str) -> bool: ...
    def already_executed(self, decision_id: str) -> bool: ...
    def mark_executed(self, decision_id: str) -> None: ...
    def verify_chain(self) -> bool: ...


class SignatureVerifier(Protocol):
    def verify(self, envelope: DecisionEnvelope) -> bool: ...


__all__ = [
    "DecisionEnvelopeRef",
    "DecisionExpired",
    "DecisionLedger",
    "MAX_REPLAY_MS",
    "SignatureVerifier",
    "SUPPORTED_ENVELOPE_VERSION",
]
