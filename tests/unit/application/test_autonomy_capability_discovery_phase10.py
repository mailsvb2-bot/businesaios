from __future__ import annotations

from dataclasses import dataclass
from types import SimpleNamespace

from application.autonomy.autonomy_state_assembly import AutonomyStateAssembly


@dataclass(frozen=True)
class _State:
    meta: dict


class _StateMapper:
    def to_world_state(self, **_kwargs):
        return _State(meta={})


class _Trace:
    run_id = "run-phase10"

    def record(self, **_kwargs):
        return None


def test_capability_discovery_is_present_before_headless_decision_planning():
    contract = SimpleNamespace(
        _state_mapper=_StateMapper(),
        _capability_health_registry=None,
        _capability_health_scoring_service=None,
        _business_memory_state_adapter=None,
        _state_store=None,
    )
    request = SimpleNamespace(
        tenant_id="tenant-1",
        business_id="business-1",
        goal="grow revenue",
        goal_id="goal-1",
        meta={},
    )

    state = AutonomyStateAssembly(contract=contract).assemble_state(
        request=request,
        trace=_Trace(),
        step_index=0,
        previous_feedback={},
        business_memory_context={},
    )

    discovery = tuple(state.meta["capability_discovery"])
    by_id = {row["capability_id"]: row for row in discovery}
    telegram = by_id["interaction.telegram"]

    assert telegram["lifecycle"] == "implemented"
    assert telegram["provider_keys"] == ["telegram_bot"]
    assert telegram["health"] == "unknown"
    assert telegram["availability"] == "unknown"
    assert telegram["approval_requirements"]["owner_approval"] is True
    assert len(by_id) == len(discovery)
