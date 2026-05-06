from __future__ import annotations

import random

class ArchitectureSearch:
    def choose_candidate(self, candidates: list[dict]) -> dict:
        if not candidates:
            return {}
        return dict(candidates[0])

    select = choose_candidate

class BayesianOptimization:
    def suggest(self, observations: list[tuple[dict, float]]):
        if not observations:
            return {}
        best = max(observations, key=lambda item: item[1])
        return dict(best[0])

class EarlyTermination:
    def stop(self, metric: float, threshold: float) -> bool:
        return metric < threshold

class EvolutionarySearch:
    def mutate(self, config: dict, mutation: dict) -> dict:
        updated = dict(config)
        updated.update(mutation)
        return updated

class PruningPolicy:
    def prune(self, scored_candidates: list[tuple[float, dict]], keep: int) -> list[tuple[float, dict]]:
        return sorted(scored_candidates, key=lambda item: item[0], reverse=True)[:keep]

class RandomSearch:
    def choose(self, space: dict[str, list]):
        return {key: random.choice(values) for key, values in space.items()}

class ResourceAllocator:
    def allocate(self, budget: int, items: int) -> list[int]:
        if items <= 0:
            return []
        share = budget // items
        return [share for _ in range(items)]

class SchedulerSearch:
    def choose(self, names: list[str]) -> str:
        if not names:
            raise ValueError("names must not be empty")
        return names[0]

_ALIAS_EXPORTS = {
    "architecture_search": "ArchitectureSearch",
    "bayesian_optimization": "BayesianOptimization",
    "early_termination": "EarlyTermination",
    "evolutionary_search": "EvolutionarySearch",
    "pruning_policy": "PruningPolicy",
    "random_search": "RandomSearch",
    "resource_allocator": "ResourceAllocator",
    "scheduler_search": "SchedulerSearch",
}

__all__ = [
    "ArchitectureSearch",
    "BayesianOptimization",
    "EarlyTermination",
    "EvolutionarySearch",
    "PruningPolicy",
    "RandomSearch",
    "ResourceAllocator",
    "SchedulerSearch",
]
