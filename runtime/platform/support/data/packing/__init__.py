from __future__ import annotations

from collections.abc import Iterable
from typing import TypeVar

T = TypeVar("T")

def balanced(items, key):
    groups = {}
    for item in items:
        groups.setdefault(key(item), []).append(item)
    out = []
    for group in groups.values():
        out.extend(group)
    return out

def build_batches(items: Iterable[T], batch_size: int) -> list[list[T]]:
    batch: list[T] = []
    out: list[list[T]] = []
    for item in items:
        batch.append(item)
        if len(batch) >= batch_size:
            out.append(batch)
            batch = []
    if batch:
        out.append(batch)
    return out

def curriculum(items, difficulty):
    return [x for x in items if getattr(x, "difficulty", 0) <= difficulty]

def shard(items, workers, worker_id):
    return items[worker_id::workers]

def hard_examples(items, threshold):
    return [x for x in items if getattr(x, "loss", 0.0) >= threshold]

def minibatches(items, batch_size):
    return build_batches(items, batch_size)

def pad_sequences(sequences, pad_value=0):
    max_len = max((len(seq) for seq in sequences), default=0)
    return [list(seq) + [pad_value] * (max_len - len(seq)) for seq in sequences]

def pack_trajectories(items, max_length):
    packed = []
    current = []
    current_len = 0
    for item in items:
        item_len = len(getattr(item, "transitions", item))
        if current and current_len + item_len > max_length:
            packed.append(current)
            current = []
            current_len = 0
        current.append(item)
        current_len += item_len
    if current:
        packed.append(current)
    return packed

__all__ = [
    "T",
    "balanced",
    "build_batches",
    "curriculum",
    "hard_examples",
    "minibatches",
    "pack_trajectories",
    "pad_sequences",
    "shard",
]
