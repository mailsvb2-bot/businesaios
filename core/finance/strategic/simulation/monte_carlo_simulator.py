from __future__ import annotations

import random
from decimal import Decimal

from config.strategic_finance_simulation_policy import (
    DEFAULT_MONTE_CARLO_SIMULATOR_POLICY,
    MonteCarloSimulatorPolicy,
)
from core.finance.strategic.decimal_utils import q2


class MonteCarloSimulator:
    """Probabilistic simulator that keeps money in Decimal.

    Randomness is sampled in basis points to avoid converting the money path
    to float before the perturbation is applied.
    """

    def __init__(self, policy: MonteCarloSimulatorPolicy = DEFAULT_MONTE_CARLO_SIMULATOR_POLICY) -> None:
        self._policy = policy

    def run(
        self,
        base_value: Decimal,
        draws: int | None = None,
        spread: Decimal | None = None,
        seed: int | None = None,
    ) -> list[Decimal]:
        total_draws = self._policy.default_draws if draws is None else draws
        spread_value = self._policy.default_spread if spread is None else spread
        random_seed = self._policy.default_seed if seed is None else seed
        rng = random.Random(random_seed)
        spread_bps = int((spread_value * self._policy.basis_points_multiplier).to_integral_value())
        results: list[Decimal] = []
        for _ in range(total_draws):
            delta_bps = rng.randint(-spread_bps, spread_bps)
            multiplier = self._policy.baseline_multiplier + (Decimal(delta_bps) / self._policy.basis_points_multiplier)
            results.append(q2(base_value * multiplier))
        return results
