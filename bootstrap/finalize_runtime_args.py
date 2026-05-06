from __future__ import annotations
CANON_BOOT_FINALIZE_RUNTIME_ARGS_FINAL_OWNER = True

CANON_BOOT_WIRING_ONLY = True


from dataclasses import dataclass
from pathlib import Path
from typing import Any

from runtime.runtime_infra import RuntimeInfra


@dataclass(frozen=True)
class FinalizeRuntimeArgs:
    stack: Any
    keyring: Any
    schemas: Any
    event_log: Any
    preg: Any
    policy_selector: Any
    handlers: Any
    model_registry: Any
    issuer_id: str
    repo_root: Path
    event_store: Any
    base: str
    runtime_infra: RuntimeInfra
