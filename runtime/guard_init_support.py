from __future__ import annotations

from threading import Lock
from typing import Any

from runtime.time import SystemClock
from runtime.platform.config.env_flags import env_str


def init_reference_mode(*, guard: Any, args: tuple[Any, ...], kwargs: dict[str, Any]) -> None:
    default_issuer = env_str("BUSINESAIOS_ISSUER_ID", "businesaios-core").strip() or "businesaios-core"
    guard._mode = "reference"
    guard._survival = args[0]
    guard._ledger = args[1]
    guard._verifier = args[2]
    guard._lock = kwargs.get("lock") or Lock()
    guard._keyring = None
    guard._schemas = None
    guard._events = None
    guard._ttl_skew_ms = 0
    guard._action_specs = None
    guard._rate_limiter = None
    guard._kill_switch = None
    guard._clock = kwargs.get("clock") or SystemClock()
    guard._expected_issuer_id = str(kwargs.get("expected_issuer_id", default_issuer) or default_issuer).strip() or default_issuer


def init_production_mode(*, guard: Any, args: tuple[Any, ...], kwargs: dict[str, Any], build_action_contract_runtime: Any, rate_limiter_factory: Any) -> None:
    keyring, ledger, schema_registry = args[0], args[1], args[2]
    event_log = kwargs.get("event_log", None)
    ttl_skew_ms = int(kwargs.get("ttl_skew_ms", 0))
    clock = kwargs.get("clock", None)
    survival_controller = kwargs.get("survival_controller", kwargs.get("survival", None))
    default_issuer = env_str("BUSINESAIOS_ISSUER_ID", "businesaios-core").strip() or "businesaios-core"
    expected_issuer_id = str(kwargs.get("expected_issuer_id", default_issuer) or default_issuer).strip() or default_issuer

    guard._mode = "production"
    guard._keyring = keyring
    guard._ledger = ledger
    guard._schemas = schema_registry
    guard._events = event_log
    guard._ttl_skew_ms = ttl_skew_ms
    guard._survival = survival_controller
    guard._clock = clock or SystemClock()
    guard._expected_issuer_id = expected_issuer_id
    guard._action_specs, guard._rate_limiter, guard._kill_switch = build_action_contract_runtime(
        kwargs=kwargs,
        rate_limiter_factory=rate_limiter_factory,
    )
    guard._lock = kwargs.get("lock") or Lock()


def require_production_mode(*, mode: str, method_name: str) -> None:
    if mode != "production":
        raise RuntimeError(f"{method_name} is only available in production mode")
