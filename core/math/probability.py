from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping


def bayes(p_b_given_a: float, p_a: float, p_b: float) -> float:
    """Bayes rule:
        P(A|B) = P(B|A) * P(A) / P(B)
    """
    if p_b <= 0:
        return 0.0
    if p_b_given_a < 0 or p_a < 0 or p_b < 0:
        raise ValueError("Probabilities must be non-negative.")
    return (p_b_given_a * p_a) / p_b


def naive_bayes_posterior(
    *,
    prior_a: float,
    likelihoods_b_given_a: Mapping[str, float],
    evidence_b: Mapping[str, float],
) -> float:
    """Naive Bayes posterior for independent evidences:
        P(A|B1..Bk) ∝ P(A) * Π P(Bi|A) / Π P(Bi)
    """
    if prior_a < 0:
        raise ValueError("prior_a must be non-negative.")
    num = prior_a
    den = 1.0
    for k, p_b_given_a in likelihoods_b_given_a.items():
        p_b = float(evidence_b.get(k, 0.0))
        if p_b_given_a < 0 or p_b < 0:
            raise ValueError("Probabilities must be non-negative.")
        num *= p_b_given_a
        den *= p_b if p_b > 0 else 0.0
    if den <= 0:
        return max(0.0, min(1.0, num))
    return max(0.0, min(1.0, num / den))


@dataclass(frozen=True)
class HistorySignals:
    """Minimal example signals for P(buy|history)."""

    sessions_7d: int
    content_completed_7d: int
    paywall_opened_7d: int
    offer_clicked_7d: int


def purchase_prob_from_history(
    history: HistorySignals,
    *,
    base_rate: float = 0.02,
    weights: dict[str, float] | None = None,
) -> float:
    """A tiny Bayesian-style heuristic (safe baseline, not a trained model):
      P(buy|user) ≈ clamp( base_rate * Π (1 + w_i * signal_i) )
    """
    if weights is None:
        weights = {
            "sessions_7d": 0.05,
            "content_completed_7d": 0.15,
            "paywall_opened_7d": 0.25,
            "offer_clicked_7d": 0.35,
        }

    if base_rate < 0:
        raise ValueError("base_rate must be non-negative.")

    score = base_rate
    score *= 1.0 + weights.get("sessions_7d", 0.0) * max(0, history.sessions_7d)
    score *= 1.0 + weights.get("content_completed_7d", 0.0) * max(0, history.content_completed_7d)
    score *= 1.0 + weights.get("paywall_opened_7d", 0.0) * max(0, history.paywall_opened_7d)
    score *= 1.0 + weights.get("offer_clicked_7d", 0.0) * max(0, history.offer_clicked_7d)
    return max(0.0, min(1.0, score))
