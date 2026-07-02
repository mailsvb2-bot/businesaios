from __future__ import annotations

from canon.anti_second_brain_runtime_rules import (
    FORBIDDEN_DIRECT_DECISION_DEPENDENCIES,
    REQUIRED_GOVERNANCE_DEPENDENCIES,
)
from canon.runtime_allowed_registrations import ALLOWED_RUNTIME_REGISTRATIONS
from runtime.errors import RuntimeConfigurationError
from runtime.manifest_entry import RuntimeManifestEntry
from runtime.service_names import RuntimeServiceName


CANON_RUNTIME_MANIFEST_VALIDATOR = True
CANON_RUNTIME_DECISION_EXECUTION_SERVICE_MANIFEST_VALIDATOR = True

_ALLOWED_MODULE_PREFIX = "boot.registrations."


def validate_runtime_manifest(entries: tuple[RuntimeManifestEntry, ...]) -> None:
    seen_steps: set[str] = set()
    seen_services: set[str] = set()

    for entry in entries:
        if entry.step_name in seen_steps:
            raise RuntimeConfigurationError(
                f"Duplicate runtime boot step '{entry.step_name}'."
            )
        seen_steps.add(entry.step_name)

        if entry.service_name in seen_services:
            raise RuntimeConfigurationError(
                f"Duplicate runtime service declaration '{entry.service_name}'."
            )
        seen_services.add(entry.service_name)

        if not entry.module_path.startswith(_ALLOWED_MODULE_PREFIX):
            raise RuntimeConfigurationError(
                f"Illegal runtime registration module '{entry.module_path}'."
            )

        if not entry.callable_name.startswith("register_"):
            raise RuntimeConfigurationError(
                f"Illegal registration callable '{entry.callable_name}'."
            )

        allowed_type = ALLOWED_RUNTIME_REGISTRATIONS.get(entry.service_name)
        if allowed_type is None:
            raise RuntimeConfigurationError(
                f"Service '{entry.service_name}' is not allowed in runtime manifest."
            )

        if allowed_type != entry.service_type:
            raise RuntimeConfigurationError(
                f"Service '{entry.service_name}' must use type '{allowed_type}', "
                f"not '{entry.service_type}'."
            )

    governance_entry = _find(entries, RuntimeServiceName.GOVERNANCE_CHAIN)
    if tuple(governance_entry.dependencies) != tuple(REQUIRED_GOVERNANCE_DEPENDENCIES):
        raise RuntimeConfigurationError(
            "Governance chain dependencies do not match canonical runtime rules."
        )

    execution_entry = _find(entries, RuntimeServiceName.RUNTIME_DECISION_EXECUTION_SERVICE)
    forbidden = FORBIDDEN_DIRECT_DECISION_DEPENDENCIES[
        RuntimeServiceName.RUNTIME_DECISION_EXECUTION_SERVICE
    ]
    illegal = [dep for dep in execution_entry.dependencies if dep in forbidden]
    if illegal:
        raise RuntimeConfigurationError(
            "Runtime decision execution service has illegal direct dependencies: "
            + ", ".join(illegal)
        )


def _find(
    entries: tuple[RuntimeManifestEntry, ...],
    service_name: str,
) -> RuntimeManifestEntry:
    for entry in entries:
        if entry.service_name == service_name:
            return entry
    raise RuntimeConfigurationError(
        f"Required runtime manifest entry '{service_name}' is missing."
    )


__all__ = [
    "CANON_RUNTIME_DECISION_EXECUTION_SERVICE_MANIFEST_VALIDATOR",
    "CANON_RUNTIME_MANIFEST_VALIDATOR",
    "validate_runtime_manifest",
]
