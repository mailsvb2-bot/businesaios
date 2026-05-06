from __future__ import annotations

from dataclasses import dataclass

from contracts.event_store import EventStore, iter_events_strict, supports_event_store


@dataclass(frozen=True)
class GovernancePathStatus:
    ok: bool
    policy_gate_events: int
    attribution_events: int
    rl_policy_events: int
    reasons: tuple[str, ...]


def assert_governance_event_store_contract(event_store: EventStore) -> None:
    missing: list[str] = []
    if not supports_event_store(event_store):
        if not hasattr(event_store, "append_event"):
            missing.append("append_event")
        if not hasattr(event_store, "iter_events"):
            missing.append("iter_events")
        if not hasattr(event_store, "count_events"):
            missing.append("count_events")
    if missing:
        raise RuntimeError("GOVERNANCE_EVENT_STORE_CONTRACT_MISSING:" + ",".join(missing))


def inspect_governance_event_path(*, event_store: EventStore, tenant_id: str = "default") -> GovernancePathStatus:
    assert_governance_event_store_contract(event_store)
    reasons: list[str] = []
    gate = attribution = rl = 0
    try:
        for event in iter_events_strict(event_store, tenant_id=tenant_id, start_ms=0, end_ms=None):
            et = str((event or {}).get("event_type") or "")
            if et.startswith(("policy_update_", "governance_policy_")):
                gate += 1
            elif et.startswith("ads_attribution_"):
                attribution += 1
            elif et.startswith("ads_rl_policy_"):
                rl += 1
    except Exception:
        reasons.append("iter_failed")
    if gate <= 0:
        reasons.append("no_policy_gate_events")
    if attribution <= 0:
        reasons.append("no_attribution_events")
    if rl <= 0:
        reasons.append("no_rl_policy_events")
    return GovernancePathStatus(len(reasons) == 0, gate, attribution, rl, tuple(reasons))
