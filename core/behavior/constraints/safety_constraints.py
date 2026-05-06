from __future__ import annotations

from core.behavior.contracts.constraints import SafetyConstraints


def derive_safety_constraints(observables: dict[str, float], policy_denials: int = 0) -> SafetyConstraints:
    anti = observables.get("anti_field_level", 0.0)
    safe_mode = anti >= 0.65 or policy_denials > 0
    return SafetyConstraints(
        safe_mode_recommended=safe_mode,
        guardrails_violation=policy_denials > 0,
    )
