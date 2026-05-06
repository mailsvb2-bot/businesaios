from __future__ import annotations
CANON_BOOT_WIRING_ONLY = True


from dataclasses import dataclass
from typing import Any, Optional

from runtime.boot import Keyring, PolicySelector

from runtime.execution.executor_state import RuntimeExecutorInfra


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
    model_registry: Optional[Any] = None
    issuer_id: str = "businesaios-core"
