from __future__ import annotations


def assert_no_hidden_selection(observables: dict[str, float]) -> None:
    forbidden = {
        "selected_offer_score",
        "winning_offer_id",
        "winner_probability",
        "chosen_price",
    }
    present = forbidden.intersection(observables.keys())
    if present:
        raise ValueError(f"Forbidden decision-like observables detected: {sorted(present)}")
