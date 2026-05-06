from __future__ import annotations


def normalize_explanations(lines: tuple[str, ...]) -> tuple[str, ...]:
    cleaned: list[str] = []
    for line in lines:
        value = str(line).strip()
        if not value:
            continue
        cleaned.append(value[:300])
    return tuple(cleaned[:20])
