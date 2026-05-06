from __future__ import annotations

from typing import Any

from runtime.governance import PolicyUpdateGate


def build_autopilot_policy_gate(*, event_store: Any | None, cooldown_ms: int = 5 * 60 * 1000) -> PolicyUpdateGate:
    gate = PolicyUpdateGate(cooldown_ms=int(cooldown_ms))
    gate.bind_event_store(event_store)
    return gate
