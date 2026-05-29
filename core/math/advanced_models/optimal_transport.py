from __future__ import annotations

from dataclasses import dataclass
from typing import List, Sequence, Tuple


@dataclass(frozen=True)
class TransportResult:
    allocation: list[list[float]]
    total_cost: float

def solve_capacity_transport(
    cost_matrix: Sequence[Sequence[float]],
    supply: Sequence[float],
    demand: Sequence[float],
) -> TransportResult:
    if not cost_matrix or not cost_matrix[0]:
        raise ValueError("cost_matrix must be non-empty")
    n_rows = len(cost_matrix)
    n_cols = len(cost_matrix[0])
    if len(supply) != n_rows:
        raise ValueError("supply length must match number of rows")
    if len(demand) != n_cols:
        raise ValueError("demand length must match number of cols")
    if abs(sum(supply) - sum(demand)) > 1e-9:
        raise ValueError("supply and demand must balance")

    remaining_supply = [float(x) for x in supply]
    remaining_demand = [float(x) for x in demand]
    allocation = [[0.0 for _ in range(n_cols)] for _ in range(n_rows)]

    edges: list[tuple[float, int, int]] = []
    for i in range(n_rows):
        for j in range(n_cols):
            edges.append((float(cost_matrix[i][j]), i, j))
    edges.sort(key=lambda t: t[0])

    total_cost = 0.0
    for cost, i, j in edges:
        moved = min(remaining_supply[i], remaining_demand[j])
        if moved <= 0:
            continue
        allocation[i][j] = moved
        remaining_supply[i] -= moved
        remaining_demand[j] -= moved
        total_cost += moved * cost

    if any(x > 1e-9 for x in remaining_supply) or any(x > 1e-9 for x in remaining_demand):
        raise RuntimeError("failed to satisfy balanced transport")
    return TransportResult(allocation=allocation, total_cost=total_cost)
