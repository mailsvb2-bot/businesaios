from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from .canonical_observation import canonicalize_trace


TRACE_IGNORED_KEYS = frozenset({"decision_id"})


@dataclass(frozen=True)
class TraceDiff:
    equal: bool
    left: dict[str, Any]
    right: dict[str, Any]
    differing_keys: tuple[str, ...]


def compare_traces(left: Mapping[str, Any] | None, right: Mapping[str, Any] | None) -> TraceDiff:
    left_trace = canonicalize_trace(left)
    right_trace = canonicalize_trace(right)
    keys = sorted((set(left_trace) | set(right_trace)) - TRACE_IGNORED_KEYS)
    differing = tuple(key for key in keys if left_trace.get(key) != right_trace.get(key))
    return TraceDiff(equal=not differing, left=left_trace, right=right_trace, differing_keys=differing)
