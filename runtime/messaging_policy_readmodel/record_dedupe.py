from __future__ import annotations


def dedupe_channels(items) -> tuple[str, ...]:
    return tuple(dict.fromkeys(str(x) for x in items if str(x).strip()))
