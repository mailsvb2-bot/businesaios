from __future__ import annotations

SUSPICIOUS_CONFIG_WORDS: tuple[str, ...] = (
    "threshold",
    "limit",
    "timeout",
    "fallback",
    "penalty",
    "weight",
    "capacity",
)


def suspicious_config_lines(text: str) -> tuple[str, ...]:
    matches: list[str] = []
    for line in text.splitlines():
        stripped = line.strip().lower()
        if "=" not in stripped:
            continue
        if any(word in stripped for word in SUSPICIOUS_CONFIG_WORDS):
            matches.append(line.strip())
    return tuple(matches)
