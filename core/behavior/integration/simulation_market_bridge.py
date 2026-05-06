from __future__ import annotations

from core.behavior.market.market_relative_state import compute_market_relative_person_state


def attach_market_context_to_simulation_result(
    simulation_result: dict[str, object],
    segment_observables: dict[str, float] | None,
    market_observables: dict[str, float] | None,
) -> dict[str, object]:
    result = dict(simulation_result)
    person_observables = dict(result.get("observables", {}))
    result["market_relative"] = compute_market_relative_person_state(
        person_observables,
        segment_observables,
        market_observables,
    )
    return result
