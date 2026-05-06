from __future__ import annotations

"""Canonical boot failure policy.

Owns the decision of whether boot-time component failures may degrade gracefully
or must fail closed. This prevents multiple helpers from embedding conflicting
fallback semantics.
"""

import logging
from typing import Any

from runtime.platform.config.env_flags import env_bool, env_str
from runtime.observability import log_exception_throttled

LOGGER = logging.getLogger(__name__)


def boot_fail_closed(*, settings: Any = None) -> bool:
    core = getattr(settings, "core", None)
    settings_env = str(getattr(core, "env", "")).strip().lower()
    settings_strict = bool(getattr(core, "production_strict_mode", False))
    env_name = (settings_env or env_str("ENV", "")).strip().lower()
    run_mode = env_str("RUN_MODE", env_str("MODE", "demo")).strip().lower()
    if env_bool("BOOT_FAIL_CLOSED", False):
        return True
    if settings_strict:
        return True
    if env_name == "prod" and env_bool("PRODUCTION_STRICT_MODE", False):
        return True
    return env_name == "prod" and run_mode not in {"demo", "test"}


def raise_or_log_boot_failure(*, component: str, exc: Exception, settings: Any = None, logger: logging.Logger | None = None) -> None:
    target_logger = logger or LOGGER
    log_exception_throttled(
        target_logger,
        key=f"boot_component_failed:{component}",
        msg=f"{component}_failed:{exc.__class__.__name__}",
    )
    if boot_fail_closed(settings=settings):
        raise RuntimeError(f"BOOT_COMPONENT_FAILED:{component}") from exc



def resolve_optional_boot_component(*, component: str, builder, fallback, settings: Any = None, logger: logging.Logger | None = None):
    try:
        return builder()
    except Exception as exc:
        raise_or_log_boot_failure(
            component=component,
            exc=exc,
            settings=settings,
            logger=logger,
        )
        return fallback
