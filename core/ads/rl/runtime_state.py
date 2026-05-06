from __future__ import annotations

from typing import Any

from core.ads.rl.policy_store import PolicyStore
from core.governance.evaluators.attribution_maturity import AttributionMaturityGate

policy_store = PolicyStore()
maturity_gate = AttributionMaturityGate(maturity_window_ms=24 * 60 * 60 * 1000)


def bind_runtime_state(*, event_store: Any | None) -> None:
    policy_store.bind_event_store(event_store)
    maturity_gate.bind_event_store(event_store)
