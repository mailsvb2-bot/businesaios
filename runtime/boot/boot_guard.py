"""Guard assembly helpers extracted from boot_core_assembly."""

from __future__ import annotations

from typing import Any

from runtime.boot import EnvFlagProvider, Keyring, KillSwitch, actions_registry
from runtime.enforcement.rate_limit import RuntimeActionRateLimiter
from runtime.guard import RuntimeGuard
from survival.controller import SurvivalController

CANON_BOOT_WIRING_ONLY = True

def build_guard(*, keyring: Keyring, ledger: Any, schemas: Any, event_log: Any, survival_controller: SurvivalController, issuer_id: str) -> RuntimeGuard:
    return RuntimeGuard(
        keyring,
        ledger,
        schemas,
        event_log=event_log,
        survival_controller=survival_controller,
        expected_issuer_id=issuer_id,
        action_specs=actions_registry,
        rate_limiter=RuntimeActionRateLimiter(),
        kill_switch=KillSwitch(EnvFlagProvider()),
    )


__all__ = ["CANON_BOOT_WIRING_ONLY", "build_guard"]
