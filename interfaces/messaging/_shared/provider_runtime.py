from __future__ import annotations

from typing import Any
from collections.abc import Callable

from interfaces.messaging._shared.adapter_base import AdapterBase
from interfaces.messaging._shared.delivery_mapper import map_delivery_result
from interfaces.messaging._shared.outbound_sender import send_outbound
from interfaces.messaging._shared.runner_base import RunnerBase
from interfaces.messaging._shared.runner_components import build_provider_config
from interfaces.messaging._shared.send_guard import guarded_send


class ProviderRunner(RunnerBase):
    """Thin canonical runner for config-driven provider channels."""

    def __init__(self, *, provider: str, env_prefix: str, default_mode: str) -> None:
        super().__init__(
            build_config=lambda: build_provider_config(
                provider=provider,
                env_prefix=env_prefix,
                default_mode=default_mode,
            ),
            send_raw=send_raw_for,
            map_result=map_result_for,
        )


class ProviderAdapter(AdapterBase):
    """Thin canonical adapter that owns exactly one provider runner."""

    def __init__(self, runner_factory: Callable[[], Any]) -> None:
        super().__init__(runner=runner_factory())


def send_raw_for(*, cfg: Any, msg: Any) -> dict:
    caller = getattr(msg, "payload", {}).get("execution_entrypoint", "") if hasattr(msg, "payload") else ""
    return guarded_send(caller=caller, send_fn=send_outbound, cfg=cfg, msg=msg)


def map_result_for(*, msg: Any, raw: dict) -> Any:
    return map_delivery_result(msg=msg, raw=raw)


def build_config_for(*, provider: str, env_prefix: str, default_mode: str):
    return build_provider_config(
        provider=provider,
        env_prefix=env_prefix,
        default_mode=default_mode,
    )
