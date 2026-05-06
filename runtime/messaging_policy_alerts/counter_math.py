from __future__ import annotations


def sum_counts(items) -> int:
    total = 0
    for item in tuple(items or ()):
        try:
            total += int(item[1])
        except Exception:
            continue
    return total


def top_share(items) -> float:
    pairs = tuple(items or ())
    if not pairs:
        return 0.0
    total = sum_counts(pairs)
    if total <= 0:
        return 0.0
    top = max(int(item[1]) for item in pairs)
    return round(float(top) / float(total), 6)


def average_attempts_per_trace(*, attempts_total: int, traces_total: int) -> float:
    den = int(traces_total or 0)
    if den <= 0:
        return 0.0
    return round(float(int(attempts_total or 0)) / float(den), 6)


def fallback_usage_rate(*, selected_channel_counts, delivered_channel_counts) -> float:
    selected_total = sum_counts(selected_channel_counts)
    delivered_total = sum_counts(delivered_channel_counts)
    if selected_total <= 0:
        return 0.0
    if delivered_total <= 0:
        return 1.0
    diff = max(0, int(selected_total) - int(delivered_total))
    return round(float(diff) / float(selected_total), 6)
