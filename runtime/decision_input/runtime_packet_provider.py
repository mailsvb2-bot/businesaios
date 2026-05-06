from __future__ import annotations

from typing import Any

from canon.decision_input_rules import assert_safe_recommendations
from runtime.decision_input.provider_call import call_decision_input_provider
from runtime.integration.decision_input_packet import DecisionInputPacket


def maybe_build_decision_input_packet(
    *,
    provider: object | None,
    world_state: Any,
    proposal: dict[str, Any] | None,
    generated_at_ms: int,
    safe_mode: bool,
) -> DecisionInputPacket | None:
    if provider is None:
        return None

    build_fn = getattr(provider, "build_decision_input_packet", None)
    if not callable(build_fn):
        return None

    packet = call_decision_input_provider(
        build_fn=build_fn,
        world_state=world_state,
        proposal=dict(proposal or {}),
        generated_at_ms=int(generated_at_ms),
        safe_mode=bool(safe_mode),
    )

    if packet is None:
        return None
    if not isinstance(packet, DecisionInputPacket):
        raise TypeError("build_decision_input_packet must return DecisionInputPacket | None")
    # Fail closed: provider must never feed decision/narrowing fields.
    assert_safe_recommendations(tuple(packet.recommendation_packet.recommendations))
    return packet
