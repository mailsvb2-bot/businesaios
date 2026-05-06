from __future__ import annotations

from canon.runtime_capability_rules import CAPABILITY_TO_ALLOWED_SERVICES


def validate_capability_access(*, capability: str, service_name: str) -> None:
    allowed = CAPABILITY_TO_ALLOWED_SERVICES.get(capability)
    if allowed is None:
        raise RuntimeError(f"Unknown runtime capability '{capability}'.")

    if service_name not in allowed:
        raise RuntimeError(
            f"Capability '{capability}' cannot access runtime service '{service_name}'."
        )
