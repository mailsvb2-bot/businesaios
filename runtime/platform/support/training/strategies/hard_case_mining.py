from __future__ import annotations


def hard_case_mining(scores: list[float], threshold: float) -> list[float]:
    return [score for score in scores if score <= threshold]

__all__ = ["hard_case_mining"]
