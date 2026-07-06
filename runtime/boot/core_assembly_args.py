from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from runtime.boot import Keyring, PolicySelector
from runtime.execution.executor_state import RuntimeExecutorInfra

CANON_BOOT_WIRING_ONLY = True

@dataclass(frozen=True)
class CoreAssemblyArgs:
    keyring: Keyring
    schemas: Any
    event_log: Any
    decision_archive: Any
    policy_registry: Any
    policy_selector: PolicySelector
    handlers: Any
    runtime_infra: RuntimeExecutorInfra
    delivery_state: Any
    model_registry: Any | None = None
    issuer_id: str = "businesaios-core"
