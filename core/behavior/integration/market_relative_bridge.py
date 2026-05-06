from __future__ import annotations

from core.behavior.market.market_relative_state import compute_market_relative_person_state


def inject_market_relative_observables(
    person_observables: dict[str, float],
    segment_observables: dict[str, float] | None,
    market_observables: dict[str, float] | None,
) -> dict[str, float]:
    result = dict(person_observables)
    result.update(compute_market_relative_person_state(person_observables, segment_observables, market_observables))
    return result
