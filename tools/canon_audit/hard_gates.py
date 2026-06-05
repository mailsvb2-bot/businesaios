from __future__ import annotations

from typing import List
from collections.abc import Sequence

from tools.canon_audit.contracts import ArchitectureViolation, HardGateResult


def evaluate_hard_gates(violations: Sequence[ArchitectureViolation]) -> list[HardGateResult]:
    codes = [v.code for v in violations]

    def gate(name: str, passed: bool, message: str) -> HardGateResult:
        return HardGateResult(name, passed, message)

    return [
        gate("single_authority", "CANON_SINGLE_AUTHORITY" not in codes and "CANON_FORMAL_AUTHORITY_LOCK" not in codes, "Every architectural authority must have exactly one owner."),
        gate("single_public_owner", "CANON_SINGLE_OWNER" not in codes and "CANON_FORMAL_OWNER_LOCK" not in codes, "Every canonical public export must have exactly one owner."),
        gate("sealed_effects", "CANON_SEALED_EFFECTS" not in codes and "CANON_EFFECT_LITERAL_OUTSIDE_SEAL" not in codes, "Effects and provider/API literals must stay inside sealed effect zone."),
        gate("no_bypass_routes", all(code not in codes for code in ("CANON_PATH_LOCK_BYPASS", "CANON_PATH_LOCK_BYPASS_CALL", "CANON_ROUTE_FORBIDDEN_CALL", "CANON_ENTRYPOINT_RUNTIME_SHORTCUT")), "Canonical execution path must be unique and bypass-free."),
        gate("no_compat", "CANON_NO_COMPAT" not in codes, "Compat is forbidden in hard Canon mode."),
        gate("no_hidden_logic", all(code not in codes for code in ("CANON_HIDDEN_NUMERIC_HEURISTIC", "CANON_POLICY_LEAKAGE", "CANON_FORMULA_OUTSIDE_POLICY")), "Policy/formula logic must stay inside semantic owners."),
        gate("no_dynamic_magic", "CANON_DYNAMIC_EXPORT_MAGIC" not in codes, "Dynamic import/export magic is forbidden in textbook-enterprise mode."),
        gate("no_policy_duplication", "CANON_POLICY_DUPLICATION" not in codes, "Policy-like formulas must not be duplicated across the codebase."),
        gate("no_noops", "CANON_NOOP_FUNCTION" not in codes, "No placeholder/runtime no-op functions are allowed."),
        gate("no_owner_misuse", all(code not in codes for code in ("CANON_OWNER_MISUSE_DECISION", "CANON_OWNER_MISUSE_EFFECT", "CANON_OWNER_MISUSE_MEMORY", "CANON_OWNER_MISUSE_EVIDENCE")), "Canonical owners must not be called from forbidden authority zones."),
        gate("no_provider_wiring_bypass", all(code not in codes for code in ("CANON_PROVIDER_WIRING_DECISION_RUNTIME", "CANON_PROVIDER_WIRING_ENTRYPOINT_EFFECT", "CANON_PROVIDER_WIRING_EFFECT_DECISION")), "Provider wiring must not create hidden alternate authority routes."),
        gate("trace_contract_complete", all(code not in codes for code in ("CANON_TRACE_CONTRACT_WEAK", "CANON_TRACE_CONTRACT_MISSING_STAGE")), "Trace contracts must cover the full canonical execution route."),
        gate("no_di_container", "CANON_DI_CONTAINER" not in codes, "Container/service-locator architecture is forbidden in hard Canon mode."),
    ]
