from __future__ import annotations

from runtime.handlers import ActionHandlerRegistry
from runtime.handlers_ops import (
    handle_admin_set_perm,
    handle_admin_set_role,
    handle_admin_user_card,
    handle_answer_callback,
    handle_apply_pricing_change,
    handle_capture_payment,
    handle_create_payment_and_send_link,
    handle_deploy_policy,
    handle_grant_access,
    handle_reconcile_payment,
    handle_reconcile_payments,
    handle_reject_pricing_change,
    handle_request_pricing_change,
    handle_rollback_policy,
    handle_select_tariff,
    handle_send_weather,
    handle_set_marketing_copy,
    handle_set_user_setting,
)

CANON_BOOT_WIRING_ONLY = True


def register_ops_handlers(*, handlers: ActionHandlerRegistry, event_store) -> None:
    handlers.register("answer_callback@v1", handle_answer_callback)
    handlers.register("send_weather@v1", handle_send_weather)
    handlers.register("set_user_setting@v1", handle_set_user_setting)
    handlers.register("admin_set_role@v1", handle_admin_set_role)
    handlers.register("admin_set_perm@v1", handle_admin_set_perm)
    handlers.register("set_marketing_copy@v1", handle_set_marketing_copy)
    handlers.register(
        "admin_user_card@v1",
        lambda payload, effects, env: handle_admin_user_card(payload, effects, env, event_store=event_store),
    )
    handlers.register("apply_pricing_change@v1", handle_apply_pricing_change)
    handlers.register("request_pricing_change@v1", handle_request_pricing_change)
    handlers.register("reject_pricing_change@v1", handle_reject_pricing_change)
    handlers.register("select_tariff@v1", handle_select_tariff)
    handlers.register("capture_payment@v1", handle_capture_payment)
    handlers.register("create_payment_and_send_link@v1", handle_create_payment_and_send_link)
    handlers.register("reconcile_payments@v1", handle_reconcile_payments)
    handlers.register("reconcile_payment@v1", handle_reconcile_payment)
    handlers.register("grant_access@v1", handle_grant_access)
    handlers.register("deploy_policy@v1", handle_deploy_policy)
    handlers.register("rollback_policy@v1", handle_rollback_policy)
