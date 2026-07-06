from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from core.scorers.pricing import choose_probabilities, sample_index


def posterior_mean_conv(*, stats: dict[int, tuple[int, int]], price: int, prior_alpha: float, prior_beta: float) -> float:
    trials_n, succ_n = stats.get(int(price), (0, 0))
    a = float(prior_alpha) + float(succ_n)
    b = float(prior_beta) + float(max(0, trials_n - succ_n))
    return float(a) / float(a + b) if (a + b) > 0 else 0.0


def choose_candidate(*, rng: Any, candidates: Sequence[int], stats: dict[int, tuple[int, int]], exploration: str, epsilon: float, temperature: float, prior_alpha: float, prior_beta: float) -> dict[str, Any]:
    means = [posterior_mean_conv(stats=stats, price=p, prior_alpha=prior_alpha, prior_beta=prior_beta) for p in candidates]
    exp_rev = [float(p) * float(m) for p, m in zip(candidates, means, strict=False)]
    probs = choose_probabilities(
        exploration=str(exploration or "softmax_v1"),
        expected_revenue=exp_rev,
        epsilon=float(epsilon),
        temperature=float(temperature),
    )
    idx = sample_index(rng, probs)
    return {
        "index": int(idx),
        "means": means,
        "expected_revenue": exp_rev,
        "probs": probs,
        "choice": int(candidates[idx]),
        "propensity": (float(probs[idx]) if probs else None),
    }



def score_candidates(candidates: Sequence[dict[str, Any]], *, evidence: dict[str, Any]) -> list[dict[str, Any]]:
    scored: list[dict[str, Any]] = []
    default_score = float(evidence.get("default_score", 0.0) or 0.0)
    for idx, candidate in enumerate(candidates):
        item = dict(candidate or {})
        score = float(item.get("score", default_score) or default_score)
        scored.append({"candidate": item, "score": score, "rank": idx})
    scored.sort(key=lambda x: (float(x.get("score", 0.0)), -int(x.get("rank", 0))), reverse=True)
    return scored
