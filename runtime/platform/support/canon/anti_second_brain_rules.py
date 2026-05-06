from __future__ import annotations

RULES = (
    "no_inline_promotion_logic",
    "no_serving_side_selection",
    "no_training_side_release",
    "no_hidden_reward_override",
    "no_decision_core_aliases",
    "no_shadow_authority_paths",
)

FORBIDDEN_SYMBOLS = {
    "promote_from_training",
    "publish_from_serving",
    "shadow_decision_core",
    "implicit_winner_selection",
}

FORBIDDEN_FILENAMES = {"brain.py", "autopilot.py", "decision_engine.py"}


def is_forbidden_symbol(name: str) -> bool:
    return name in FORBIDDEN_SYMBOLS


def is_forbidden_filename(name: str) -> bool:
    return name in FORBIDDEN_FILENAMES

__all__ = [
    "FORBIDDEN_FILENAMES",
    "FORBIDDEN_SYMBOLS",
    "RULES",
    "is_forbidden_filename",
    "is_forbidden_symbol",
]
