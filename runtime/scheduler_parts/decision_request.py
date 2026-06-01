from __future__ import annotations

"""Canonical scheduler decision-request helper.

This module keeps scheduler-side decision execution on one path:
proposal/world-state -> decision input packet -> runtime decision gateway -> executor.
It contains no raw decision logic and does not construct alternate decision owners.
"""

from typing import Any, Mapping

from runtime.decision_gateway import execute_runtime_decision
from runtime.decision_input.runtime_packet_provider import maybe_build_decision_input_packet

CANON_RUNTIME_SCHEDULER_DECISION_REQUEST_SINGLE_PATH = True
CANON_RUNTIME_SCHEDULER_DECISION_REQUEST_NO_RAW_DECISION_LOGIC = True
CANON_RUNTIME_SCHEDULER_DECISION_REQUEST_GATEWAY_ONLY = True
CANON_RUNTIME_SCHEDULER_DECISION_REQUEST_GATEWAY_EXECUTION_OWNER = True


def request_scheduler_decision_execution(
    *,
    issuer: Any,
    executor: Any,
    world_state: Any,
    proposal: Mapping[str, object],
    generated_at_ms: int,
    safe_mode: bool,
    decision_input_provider: object | None = None,
) -> Any:
    packet = maybe_build_decision_input_packet(
        provider=decision_input_provider,
        world_state=world_state,
        proposal=dict(proposal),
        generated_at_ms=int(generated_at_ms),
        safe_mode=bool(safe_mode),
    )
    return execute_runtime_decision(
        issuer=issuer,
        executor=executor,
        state=world_state,
        decision_input_packet=packet,
    )
