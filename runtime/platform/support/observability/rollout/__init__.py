from __future__ import annotations

"""Canonical rollout observability surface with compat alias submodules."""

class ActorMetrics:
    def summarize(self, actors: int) -> dict[str, int]:
        return {"actors": actors}

class CollectorMetrics:
    def summarize(self, collected: int) -> dict[str, int]:
        return {"collected": collected}

class EpisodeMetrics:
    def summarize(self, rewards: list[float]) -> dict[str, float]:
        if not rewards:
            return {"episode_reward": 0.0}
        return {"episode_reward": sum(rewards)}

class RewardMetrics:
    def summarize(self, rewards: list[float]) -> dict[str, float]:
        if not rewards:
            return {"average_reward": 0.0}
        return {"average_reward": sum(rewards) / len(rewards)}

class RolloutMetricsView:
    def summarize(self, episodes: int, transitions: int) -> dict[str, int]:
        return {"episodes": episodes, "transitions": transitions}

_ALIAS_EXPORTS = {
    "actor_metrics": "ActorMetrics",
    "collector_metrics": "CollectorMetrics",
    "episode_metrics": "EpisodeMetrics",
    "reward_metrics": "RewardMetrics",
    "rollout_metrics": "RolloutMetricsView",
}

__all__ = [
    "ActorMetrics",
    "CollectorMetrics",
    "EpisodeMetrics",
    "RewardMetrics",
    "RolloutMetricsView",
] + list(_ALIAS_EXPORTS)
