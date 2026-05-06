from __future__ import annotations

from collections.abc import Sequence
from typing import TypeVar

T = TypeVar("T")

def encode_categorical(value, vocabulary):
    return vocabulary.get(value, vocabulary.get("<unk>", -1))

def build_features(obs):
    return obs

def bridge_to_feature_store(features):
    return dict(features)

def fill_missing(mapping, default=0):
    return {k: (default if v is None else v) for k, v in mapping.items()}

class RunningMeanStd:
    def __init__(self):
        self.mean = 0.0
        self.count = 0

    def update(self, value):
        self.count += 1
        self.mean += (value - self.mean) / self.count

def normalize_observation(obs, stats=None):
    return obs if stats is None else {k: (v - stats.get(k, 0.0)) for k, v in obs.items()}

def transform_reward(reward, scale=1.0):
    return reward * scale

def sequence_windows(items: Sequence[T], window: int) -> list[Sequence[T]]:
    if window <= 0:
        return []
    return [items[i : i + window] for i in range(0, max(0, len(items) - window + 1))]

__all__ = [
    "T",
    "RunningMeanStd",
    "bridge_to_feature_store",
    "build_features",
    "encode_categorical",
    "fill_missing",
    "normalize_observation",
    "sequence_windows",
    "transform_reward",
]
