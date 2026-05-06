from runtime.boot.actions_registry import INLINE_ALLOWLIST, SPECS


def test_ops_and_messaging_actions_have_real_handler_refs() -> None:
    for action in [
        "admin_set_perm@v1",
        "admin_set_role@v1",
        "admin_user_card@v1",
        "answer_callback@v1",
        "apply_pricing_change@v1",
        "capture_payment@v1",
        "create_payment_and_send_link@v1",
        "grant_access@v1",
        "log_mood@v1",
        "noop@v1",
        "one_click_value@v1",
        "reconcile_payment@v1",
        "reconcile_payments@v1",
        "reject_pricing_change@v1",
        "request_pricing_change@v1",
        "rollback_policy@v1",
        "select_tariff@v1",
        "send_audio@v1",
        "send_marketing_offer@v1",
        "send_message@v1",
        "send_weather@v1",
        "set_marketing_copy@v1",
        "set_user_setting@v1",
        "telegram_self_check@v1",
    ]:
        spec = SPECS[action]
        assert action not in INLINE_ALLOWLIST
        assert spec.handler_ref.startswith(("runtime.handlers.", "runtime.handlers_"))
