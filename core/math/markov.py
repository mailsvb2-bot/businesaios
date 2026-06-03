from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Mapping


def estimate_transition_counts(sequences: Iterable[list[str]]) -> dict[tuple[str, str], int]:
    """Estimate transition counts count(S_t -> S_{t+1})."""
    counts: dict[tuple[str, str], int] = defaultdict(int)
    for seq in sequences:
        if not seq or len(seq) < 2:
            continue
        for a, b in zip(seq[:-1], seq[1:], strict=False):
            counts[(a, b)] += 1
    return dict(counts)


def normalize_transition_counts(counts: Mapping[tuple[str, str], int]) -> dict[str, dict[str, float]]:
    """Convert counts to probabilities P(next|state)."""
    totals: dict[str, int] = defaultdict(int)
    for (a, _b), c in counts.items():
        totals[a] += int(c)
    out: dict[str, dict[str, float]] = defaultdict(dict)
    for (a, b), c in counts.items():
        den = totals[a]
        out[a][b] = (float(c) / den) if den > 0 else 0.0
    return dict(out)


def next_state_distribution(
    transition: Mapping[str, Mapping[str, float]],
    state: str,
) -> dict[str, float]:
    """P(S_{t+1} | S_t=state) as a dict."""
    return dict(transition.get(state, {}))
