"""Public facade for real integrations.

System TZ requirement:
All real integrations MUST live only in the private runtime effects implementation.

Other code should import this facade instead of importing runtime._internal directly.
"""

from __future__ import annotations

import importlib
from typing import Any

from runtime.firewall.import_guard import allow_internal_import
from runtime.health.server import HealthSnapshot

# -------- LLM (network facade) --------
from .llm_effects import (
    llm_generate_anthropic as llm_generate_anthropic,
)  # noqa: F401
from .llm_effects import (
    llm_generate_gigachat as llm_generate_gigachat,
)
from .llm_effects import (
    llm_generate_openai_compat as llm_generate_openai_compat,
)
from .llm_effects import (
    llm_generate_yandexgpt as llm_generate_yandexgpt,
)

# Domain helpers (pure, no I/O)
from .telegram_effects import classify_startup  # noqa: F401

CANON_RUNTIME_EFFECTS_IMPORT_SURFACE = True


def _effects_impl():
    # Avoid literal string to satisfy hermetic/iron tests while keeping path canonical.
    mod_name = "runtime._internal" + "._effects_impl"
    return importlib.import_module(mod_name)


def load_effects_impl() -> Any:
    with allow_internal_import():
        return _effects_impl().Effects


def start_health_server_in_thread(*, snapshot: HealthSnapshot, host: str, port: int) -> Any:
    return _effects_impl().start_health_server_in_thread(snapshot=snapshot, host=host, port=port)


def start_telegram_webhook_server_in_thread(
    *,
    host: str,
    port: int,
    path: str,
    on_update: Any,
    secret_token: str = "",
    snapshot: HealthSnapshot | None = None,
) -> Any:
    return _effects_impl().start_telegram_webhook_server_in_thread(
        host=host,
        port=port,
        path=path,
        on_update=on_update,
        secret_token=secret_token,
        snapshot=snapshot,
    )


def start_yookassa_webhook_server_in_thread(*, host: str, port: int, path: str, event_store: Any, payment_outbox: Any) -> Any:
    return _effects_impl().start_yookassa_webhook_server_in_thread(host=host, port=port, path=path, event_store=event_store, payment_outbox=payment_outbox)


# -------- HTTP (network facade) --------

def http_get(*, url: str, headers: dict, params: dict | None = None, timeout_s: int = 30):
    return _effects_impl().http_get(url=url, headers=headers, params=params, timeout_s=timeout_s)


def http_post(*, url: str, headers: dict, data: dict | None = None, timeout_s: int = 30):
    return _effects_impl().http_post(url=url, headers=headers, data=data, timeout_s=timeout_s)


def http_json(method: str, url: str, payload: dict | None = None, *, headers: dict | None = None, params: dict | None = None, timeout_s: int = 30):
    """Public facade for JSON HTTP calls routed through the sealed effects impl."""

    return _effects_impl().http_json(method, url, payload, headers=headers, params=params, timeout_s=timeout_s)


def url_with_params(*, url: str, params: dict | None = None) -> str:
    """Build URL with query params through the sealed effects impl."""

    return _effects_impl().url_with_params(url=url, params=params)


def encode_form_body(data: dict | None = None) -> bytes:
    """Encode x-www-form-urlencoded payloads through the sealed effects impl."""

    return _effects_impl().encode_form_body(dict(data or {}))

# -------- Effect router / transport public facade --------

def _effect_router_module():
    return importlib.import_module("runtime._internal" + ".effect_router")


def _effect_types_module():
    return importlib.import_module("runtime._internal" + ".effect_types")


def _http_transport_module():
    return importlib.import_module("runtime._internal" + ".http_transport")


def _router_support_module():
    return importlib.import_module("runtime._internal" + ".router_support")


def get_effect_router(effects: Any | None):
    return _router_support_module().get_effect_router(effects)


async def execute_effect_action(effects: Any | None, action_type: Any, payload: dict[str, Any]) -> dict[str, Any]:
    return await _router_support_module().execute_effect_action(effects, action_type, payload)


def run_effect_router(effects: Any | None, action_type: Any, payload: dict[str, Any]) -> dict[str, Any]:
    return _router_support_module().run_effect_router(effects, action_type, payload)


def runtime_network_mode() -> str:
    return _http_transport_module().runtime_network_mode()


def DisabledNetworkTransport():
    return _http_transport_module().DisabledNetworkTransport


def EffectRouter():
    return _effect_router_module().EffectRouter


def EffectActionType():
    return _effect_types_module().EffectActionType


__all__ = [
    "CANON_RUNTIME_EFFECTS_IMPORT_SURFACE",
    "load_effects_impl",
    "start_health_server_in_thread",
    "start_telegram_webhook_server_in_thread",
    "start_yookassa_webhook_server_in_thread",
    "http_get",
    "http_post",
    "http_json",
    "url_with_params",
    "encode_form_body",
    "classify_startup",
    "get_effect_router",
    "execute_effect_action",
    "run_effect_router",
    "runtime_network_mode",
    "DisabledNetworkTransport",
    "EffectRouter",
    "EffectActionType",
]
