from __future__ import annotations

"""Shared signal normalization for Growth.

Keeps score/channel/action inference in one place so detect / rank / assemble do not
carry divergent fallback rules.
"""

from typing import Mapping


def normalize_signal(signal: Mapping[str, object] | None) -> dict[str, object]:
    return dict(signal or {})


def signal_score(signal: Mapping[str, object] | None) -> float:
    normalized = normalize_signal(signal)
    for key in ("score", "intent_score", "expected_value"):
        value = normalized.get(key)
        try:
            return float(value)
        except (TypeError, ValueError):
            continue
    return 0.0


def signal_channel(signal: Mapping[str, object] | None) -> str:
    normalized = normalize_signal(signal)
    value = str(normalized.get("channel", normalized.get("source", "unknown"))).strip()
    return value or "unknown"


def signal_action_type(signal: Mapping[str, object] | None) -> str:
    normalized = normalize_signal(signal)
    value = str(normalized.get("action_type", "notify_owner")).strip()
    return value or "notify_owner"


def signal_expected_value(signal: Mapping[str, object] | None, *, default: float) -> float:
    normalized = normalize_signal(signal)
    value = normalized.get("expected_value", default)
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def signal_confidence(signal: Mapping[str, object] | None, *, default: float) -> float:
    normalized = normalize_signal(signal)
    value = normalized.get("confidence", default)
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


__all__ = [
    "normalize_signal",
    "signal_action_type",
    "signal_channel",
    "signal_confidence",
    "signal_expected_value",
    "signal_score",
]
