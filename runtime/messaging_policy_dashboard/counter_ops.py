from __future__ import annotations


def increment(counter: dict[str, int], key: str) -> None:
    text = str(key or '').strip()
    if not text:
        return
    counter[text] = int(counter.get(text, 0)) + 1


def sorted_counter_items(counter: dict[str, int]) -> tuple[tuple[str, int], ...]:
    return tuple(sorted(counter.items(), key=lambda x: (-int(x[1]), str(x[0]))))
