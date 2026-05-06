from __future__ import annotations

"""Action handler registry.

This file groups effect handlers by domain modules.
"""

from types import MappingProxyType
from typing import Callable, Dict, Mapping

ActionHandler = Callable[..., object]


def build_registry(effects_impl) -> Mapping[str, ActionHandler]:
    reg: Dict[str, ActionHandler] = {
        "send_message@v1": effects_impl.send_message,
        "compose_marketing_message@v1": effects_impl.compose_marketing_message,
        "send_audio@v1": effects_impl.send_audio,
        "send_weather@v1": effects_impl.send_weather,
        "set_user_setting@v1": effects_impl.set_user_setting,
        "apply_offer_patch@v1": effects_impl.apply_offer_patch,
        "suggest_offer_patch@v1": effects_impl.suggest_offer_patch,
        "log_mood@v1": effects_impl.log_mood,
        "admin_set_role@v1": effects_impl.admin_set_role,
        "admin_set_perm@v1": effects_impl.admin_set_perm,
        "set_marketing_copy@v1": effects_impl.set_marketing_copy,
        "record_variant_shown@v1": effects_impl.record_variant_shown,
        "record_variant_chosen@v1": effects_impl.record_variant_chosen,
        "enqueue_evolution_job@v1": effects_impl.enqueue_evolution_job,
        "select_tariff@v1": effects_impl.select_tariff,
        "capture_payment@v1": effects_impl.capture_payment,
        "reconcile_payments@v1": effects_impl.reconcile_payments,
        "reconcile_payment@v1": effects_impl.reconcile_payment,
        "grant_access@v1": effects_impl.grant_access,
        "deploy_policy@v1": effects_impl.deploy_policy,
        "rollback_policy@v1": effects_impl.rollback_policy,
        "poll_telegram_updates@v1": effects_impl.poll_telegram_updates,
        "telegram_self_check@v1": effects_impl.telegram_self_check,
    }
    # Freeze registry to prevent accidental runtime mutation.
    return MappingProxyType(reg)
