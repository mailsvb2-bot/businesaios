from __future__ import annotations

"""Final owner for system registry boot helpers."""

from shared.registry import (
    ActionRunnerRegistry,
    ConnectorRegistry,
    ExperimentRegistry,
    ModelRegistry,
    PolicyRegistry,
    TemplateRegistry,
)

CANON_BOOT_SYSTEM_REGISTRY_FINAL_OWNER = True
CANON_BOOT_SYSTEM_REGISTRY_INTERNAL_SUPPORT = True
CANON_BOOT_SYSTEM_REGISTRY_NO_RUNTIME_ASSEMBLY = True
CANONICAL_OWNER_BOOTSTRAP_PUBLIC_API = "runtime.bootstrap"


def build_system_registries() -> dict[str, object]:
    return {
        "connectors": ConnectorRegistry(),
        "action_runners": ActionRunnerRegistry(),
        "policies": PolicyRegistry(),
        "models": ModelRegistry(),
        "templates": TemplateRegistry(),
        "experiments": ExperimentRegistry(),
    }
