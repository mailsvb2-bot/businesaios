from __future__ import annotations

from dataclasses import dataclass
from collections.abc import Sequence

from canon.simplification_constitution import (
    SimplificationClass,
    SimplificationIntent,
    SimplificationVerdict,
)


@dataclass(frozen=True)
class LayerAssessment:
    """Structured description of a layer before simplification."""

    name: str
    layer_class: SimplificationClass
    has_real_domain_logic: bool
    enforces_safety_invariant: bool
    enforces_decision_discipline: bool
    preserves_observability: bool
    is_public_contract: bool
    is_duplicate_of: str | None = None
    only_proxies_data: bool = False
    only_relabels_fields: bool = False
    only_rebuilds_same_keys: bool = False
    creates_synthetic_fallback_truth: bool = False
    creates_parallel_path: bool = False


@dataclass(frozen=True)
class SimplificationProposal:
    """Proposal that must be evaluated before radical collapse work."""

    target: str
    intent: SimplificationIntent
    assessments: Sequence[LayerAssessment]
    expected_verdict: SimplificationVerdict
    preserves_functionality: bool
    preserves_decision_discipline: bool
    preserves_safety: bool
    preserves_observability: bool
    preserves_domain_boundaries: bool
    regression_tests_added: bool
    preserves_architectural_locks: bool = True
    preserves_lock_signal_localization: bool = True
    notes: str = ""


@dataclass(frozen=True)
class SimplificationEvaluation:
    accepted: bool
    verdict: SimplificationVerdict
    violations: tuple[str, ...]


def classify_layer_for_simplification(layer: LayerAssessment) -> SimplificationVerdict:
    """Strictly classify whether a layer may be simplified."""

    if layer.has_real_domain_logic:
        return SimplificationVerdict.KEEP

    if layer.enforces_decision_discipline:
        return SimplificationVerdict.KEEP

    if layer.enforces_safety_invariant:
        return SimplificationVerdict.KEEP

    if layer.preserves_observability:
        return SimplificationVerdict.KEEP

    if layer.is_public_contract:
        return SimplificationVerdict.KEEP_AS_THIN_ADAPTER

    if layer.creates_parallel_path or layer.creates_synthetic_fallback_truth:
        return SimplificationVerdict.DELETE_AS_DUPLICATE

    if layer.only_proxies_data or layer.only_relabels_fields or layer.only_rebuilds_same_keys:
        return SimplificationVerdict.MERGE_INTO_NEIGHBOR

    if layer.is_duplicate_of:
        return SimplificationVerdict.DELETE_AS_DUPLICATE

    return SimplificationVerdict.KEEP


def evaluate_simplification(proposal: SimplificationProposal) -> SimplificationEvaluation:
    violations: list[str] = []

    if not proposal.preserves_functionality:
        violations.append("functional_regression_forbidden")
    if not proposal.preserves_decision_discipline:
        violations.append("decision_discipline_regression_forbidden")
    if not proposal.preserves_safety:
        violations.append("safety_regression_forbidden")
    if not proposal.preserves_observability:
        violations.append("observability_regression_forbidden")
    if not proposal.preserves_domain_boundaries:
        violations.append("domain_boundary_regression_forbidden")
    if not proposal.regression_tests_added:
        violations.append("regression_lock_required")
    if not proposal.preserves_architectural_locks:
        violations.append("architectural_lock_blur_forbidden")
    if not proposal.preserves_lock_signal_localization:
        violations.append("architectural_lock_signal_localization_required")

    for layer in proposal.assessments:
        verdict = classify_layer_for_simplification(layer)

        if verdict == SimplificationVerdict.KEEP and proposal.intent in {
            SimplificationIntent.DELETE,
            SimplificationIntent.MERGE,
            SimplificationIntent.INLINE,
        }:
            violations.append(f"cannot_simplify_meaningful_layer:{layer.name}")

        if layer.creates_parallel_path and proposal.intent not in {
            SimplificationIntent.DELETE,
            SimplificationIntent.MERGE,
            SimplificationIntent.GUARD_HARDEN,
        }:
            violations.append(f"parallel_path_must_be_eliminated:{layer.name}")

        if layer.creates_synthetic_fallback_truth and proposal.intent not in {
            SimplificationIntent.DELETE,
            SimplificationIntent.MERGE,
            SimplificationIntent.SAFETY_HARDEN,
        }:
            violations.append(f"synthetic_fallback_truth_must_be_eliminated:{layer.name}")

    accepted = not violations
    return SimplificationEvaluation(
        accepted=accepted,
        verdict=proposal.expected_verdict if accepted else SimplificationVerdict.REJECT_CHANGE,
        violations=tuple(violations),
    )


def assert_canon_simplification(proposal: SimplificationProposal) -> None:
    evaluation = evaluate_simplification(proposal)
    if evaluation.accepted:
        return
    joined = ", ".join(evaluation.violations)
    raise ValueError(f"Canon simplification rejected: {joined}")


def detect_parasitic_glue(layer: LayerAssessment) -> bool:
    return (
        not layer.has_real_domain_logic
        and not layer.enforces_safety_invariant
        and not layer.enforces_decision_discipline
        and not layer.preserves_observability
        and (
            layer.only_proxies_data
            or layer.only_relabels_fields
            or layer.only_rebuilds_same_keys
            or layer.is_duplicate_of is not None
        )
    )


def must_fail_closed_when_scope_missing(layer_name: str, scope_value: str | None) -> None:
    if scope_value is None or not str(scope_value).strip():
        raise ValueError(f"{layer_name}: missing_required_scope_fail_closed")
