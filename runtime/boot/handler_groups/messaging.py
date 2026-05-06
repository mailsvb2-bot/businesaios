from __future__ import annotations

CANON_BOOT_WIRING_ONLY = True


from runtime.handlers import ActionHandlerRegistry
from runtime.handlers_messaging import (
    handle_noop,
    handle_one_click_value,
    handle_poll_telegram_updates,
    handle_send_marketing_offer,
    handle_send_message,
    handle_telegram_self_check,
)


def _marketing_offer_handler(*, composer):
    def _handler(payload, effects, env):
        return handle_send_marketing_offer(payload, effects, env, composer=composer)

    return _handler



def _one_click_value_handler(*, composer):
    def _handler(payload, effects, env):
        return handle_one_click_value(payload, effects, env, composer=composer)

    return _handler



def register_messaging_handlers(*, handlers: ActionHandlerRegistry, composer) -> None:
    handlers.register("noop@v1", handle_noop)
    handlers.register("poll_telegram_updates@v1", handle_poll_telegram_updates)
    handlers.register("telegram_self_check@v1", handle_telegram_self_check)
    handlers.register("send_message@v1", handle_send_message)
    handlers.register("send_marketing_offer@v1", _marketing_offer_handler(composer=composer))
    handlers.register("one_click_value@v1", _one_click_value_handler(composer=composer))
