from __future__ import annotations

from application.world_state.history_sample import HistorySample


def _last_two(samples: tuple[HistorySample, ...]) -> tuple[HistorySample, HistorySample] | None:
    if len(samples) < 2:
        return None
    return samples[-2], samples[-1]


def scalarized_reward_delta(samples: tuple[HistorySample, ...]) -> float:
    pair = _last_two(samples)
    if pair is None:
        return 0.0
    older, newer = pair
    return float(newer.world_state.reward_state.get("scalarized_value", 0.0)) - float(older.world_state.reward_state.get("scalarized_value", 0.0))


def top_expected_value_delta(samples: tuple[HistorySample, ...]) -> float:
    pair = _last_two(samples)
    if pair is None:
        return 0.0
    older, newer = pair
    return float(newer.world_state.creative_state.get("top_expected_value_score", 0.0)) - float(older.world_state.creative_state.get("top_expected_value_score", 0.0))
