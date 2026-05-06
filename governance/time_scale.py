from __future__ import annotations

from enum import Enum, auto
from dataclasses import dataclass


class TimeScale(Enum):
    RUNTIME = auto()
    ONLINE_LEARNING = auto()
    OFFLINE_TRAINING = auto()
    EVOLUTION = auto()


@dataclass(frozen=True)
class TimeScalePolicy:
    allow_side_effects: bool
    allow_model_update: bool
    require_human_review: bool


TIME_SCALE_RULES = {
    TimeScale.RUNTIME: TimeScalePolicy(
        allow_side_effects=True,
        allow_model_update=False,
        require_human_review=False,
    ),
    TimeScale.ONLINE_LEARNING: TimeScalePolicy(
        allow_side_effects=False,
        allow_model_update=True,
        require_human_review=False,
    ),
    TimeScale.OFFLINE_TRAINING: TimeScalePolicy(
        allow_side_effects=False,
        allow_model_update=True,
        require_human_review=False,
    ),
    TimeScale.EVOLUTION: TimeScalePolicy(
        allow_side_effects=False,
        allow_model_update=True,
        require_human_review=True,
    ),
}

"""TimeScale governance.

Important invariants:
1) Runtime loop must be explicit allowlist-only.
2) Evolution actions must not leak into runtime loop.

Note: Some modules in this repo import from `governance.time_scale`.
We also provide a compatibility re-export at `core/governance/time_scale.py`.
"""


# --- PATCH 0 (requested canonical block) ---
# A minimal, explicit allowlist for *runtime* actions. This is the authoritative
# subset that must never be blocked by the runtime guard (admin actions, hooks).
RUNTIME_ACTIONS = {
    # --- UX / Telegram ---
    "send_message@v1",
    "edit_message@v1",
    "delete_message@v1",

    # --- Admin (runtime operator actions) ---
    "admin_user_card@v1",
    "admin_set_role@v1",
    "admin_set_perm@v1",

    # --- Payments / Entitlements ---
    "grant_entitlement@v1",
    "revoke_entitlement@v1",

    # --- Marketing runtime hooks ---
    "record_variant_shown@v1",
    "record_variant_chosen@v1",

    # --- Evolution scheduling ---
    "enqueue_evolution_job@v1",
}


# Project-specific runtime actions that are also safe on the fast loop.
# This keeps the system functional without weakening the requested invariants.
_RUNTIME_ACTIONS_EXTRA = {
    "noop@v1",
    "send_audio@v1",
    "send_weather@v1",
    "poll_telegram_updates@v1",
    "telegram_self_check@v1",
    "set_marketing_copy@v1",
    "capture_payment@v1",
    "create_payment_and_send_link@v1",
    "reconcile_payments@v1",
    "reconcile_payment@v1",
    "grant_access@v1",
    "set_user_setting@v1",
    "apply_offer_patch@v1",
    "suggest_offer_patch@v1",
    "log_mood@v1",
    "select_tariff@v1",
    "deploy_policy@v1",
    "rollback_policy@v1",
}


# Explicit action allowlist per timescale (hard fail otherwise).
# This prevents running expensive/dangerous effects on fast loops.
ACTION_TIME_SCALE_ALLOWLIST = {
    TimeScale.RUNTIME: set(RUNTIME_ACTIONS) | _RUNTIME_ACTIONS_EXTRA,
    TimeScale.ONLINE_LEARNING: {"noop@v1"},
    TimeScale.OFFLINE_TRAINING: {"noop@v1"},
    TimeScale.EVOLUTION: {"noop@v1", "deploy_policy@v1", "rollback_policy@v1"},
}


def assert_action_allowed(action: str, timescale: TimeScale) -> None:
    allowed = ACTION_TIME_SCALE_ALLOWLIST.get(timescale, set())
    if str(action) not in allowed:
        raise RuntimeError(f"ACTION_FORBIDDEN_ON_TIMESCALE:{action}:{timescale}")
