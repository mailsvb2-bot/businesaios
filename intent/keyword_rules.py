from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class KeywordRule:
    value: str
    keywords: tuple[str, ...]


def detect_keyword_value(*, text: str, rules: tuple[KeywordRule, ...], default: str) -> str:
    lowered = str(text or '').lower()
    for rule in rules:
        if any(keyword in lowered for keyword in rule.keywords):
            return rule.value
    return default
