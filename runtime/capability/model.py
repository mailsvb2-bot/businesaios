"""Capability mapping (runtime-only).

This module MUST NOT contain provider-specific integration strings.
It only maps canonical actions to abstract capabilities.
"""

from dataclasses import dataclass

from runtime.decision import DecisionEnvelope


@dataclass(frozen=True)
class Capability:
    name: str
    required_secret_keys: list[str]


class CapabilityResolver:
    """Maps decision → capability (runtime-only knowledge)."""

    def resolve(self, envelope: DecisionEnvelope) -> Capability:
        action = envelope.decision.action

        # Abstract capabilities — provider-specific details live ONLY in sealed effects.
        if action in {"create_payment@v1", "capture_payment@v1", "payment@v1"}:
            return Capability("payment", ["PAYMENT_PROVIDER_CREDENTIALS"])

        if action in {"send_message@v1", "message@v1"}:
            return Capability("message", ["MESSAGING_PROVIDER_CREDENTIALS"])

        return Capability("generic", [])
