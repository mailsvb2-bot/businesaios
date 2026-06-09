from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from enum import Enum
from typing import Final

CANON_SIMPLIFICATION_CONSTITUTION_VERSION: Final[str] = "1.0"


class SimplificationIntent(str, Enum):
    """Type of proposed simplification."""

    DELETE = "delete"
    MERGE = "merge"
    INLINE = "inline"
    EXTRACT = "extract"
    RENAME = "rename"
    GUARD_HARDEN = "guard_harden"
    OBSERVABILITY_HARDEN = "observability_harden"
    SAFETY_HARDEN = "safety_harden"
    DOMAIN_SEPARATION = "domain_separation"


class SimplificationClass(str, Enum):
    """Architectural role of a layer under review."""

    DOMAIN_LOGIC = "domain_logic"
    DECISION_DISCIPLINE = "decision_discipline"
    SAFETY_LOGIC = "safety_logic"
    OBSERVABILITY = "observability"
    BOUNDARY_ADAPTER = "boundary_adapter"
    TRANSPORT = "transport"
    PERSISTENCE = "persistence"
    PROXY_GLUE = "proxy_glue"
    COMPAT_SHIM = "compat_shim"
    FALLBACK = "fallback"
    RENDERING = "rendering"
    CONFIG = "config"
    TEST_LOCK = "test_lock"


class SimplificationVerdict(str, Enum):
    """Allowed disposition for a layer."""

    KEEP = "keep"
    MERGE_INTO_NEIGHBOR = "merge_into_neighbor"
    DELETE_AS_DUPLICATE = "delete_as_duplicate"
    KEEP_AS_THIN_ADAPTER = "keep_as_thin_adapter"
    REJECT_CHANGE = "reject_change"


@dataclass(frozen=True)
class CanonInvariant:
    name: str
    description: str


@dataclass(frozen=True)
class SimplificationRule:
    code: str
    title: str
    description: str


DECISION_DISCIPLINE_INVARIANTS: Final[tuple[CanonInvariant, ...]] = (
    CanonInvariant(
        name="single_decision_path",
        description=(
            "There is exactly one canonical decision path: "
            "DecisionCore -> RuntimeExecutor -> guarded bounded effects."
        ),
    ),
    CanonInvariant(
        name="no_decisioncore_bypass",
        description=(
            "No runtime, domain, policy, boot, or compatibility path may emit "
            "decision-like behavior outside the DecisionCore path."
        ),
    ),
    CanonInvariant(
        name="route_discipline",
        description=(
            "All route-critical actions must preserve strict route discipline, "
            "including decision_id and correlation_id continuity."
        ),
    ),
    CanonInvariant(
        name="guarded_execution",
        description=(
            "All risky or externally visible effects must execute only through "
            "guarded execution boundaries."
        ),
    ),
)

SAFETY_INVARIANTS: Final[tuple[CanonInvariant, ...]] = (
    CanonInvariant(
        name="stop_loss_preserved",
        description="Stop-loss logic cannot be weakened, bypassed, or made optional.",
    ),
    CanonInvariant(
        name="policy_gates_preserved",
        description="Policy gates must remain mandatory and may not be replaced by permissive fallback paths.",
    ),
    CanonInvariant(
        name="fail_closed_preserved",
        description="When scope, identity, route, or required inputs are missing, the system must fail closed.",
    ),
    CanonInvariant(
        name="tenant_hard_gates_preserved",
        description="Placeholder tenant identities must never masquerade as real business tenants.",
    ),
    CanonInvariant(
        name="schema_validation_preserved",
        description="Schema validation of action payloads is mandatory and cannot be removed for convenience.",
    ),
)

OBSERVABILITY_INVARIANTS: Final[tuple[CanonInvariant, ...]] = (
    CanonInvariant(name="trace_ids_preserved", description="Trace ids must survive all critical paths."),
    CanonInvariant(
        name="correlation_ids_preserved",
        description="Correlation ids must survive all critical paths.",
    ),
    CanonInvariant(name="snapshots_preserved", description="Snapshots and state projections must be preserved."),
    CanonInvariant(
        name="event_history_preserved",
        description="Event history and audit discipline cannot be removed in the name of simplicity.",
    ),
    CanonInvariant(
        name="decision_archive_preserved",
        description="Decision archive and its replayability must be preserved.",
    ),
)

DOMAIN_BOUNDARY_INVARIANTS: Final[tuple[CanonInvariant, ...]] = (
    CanonInvariant(
        name="no_domain_soup",
        description=(
            "Distinct domains must not be collapsed into a universal soup: retention, offers, messaging policy, "
            "ads autopilot, and behavior/operator logic must remain genuinely separated."
        ),
    ),
    CanonInvariant(
        name="domain_boundaries_preserved",
        description="Real domain boundaries must survive simplification.",
    ),
)

SIMPLIFICATION_RULES: Final[tuple[SimplificationRule, ...]] = (
    SimplificationRule(
        code="SIMPLIFY-001",
        title="Collapse form, not meaning",
        description=(
            "Only duplicate routes, parasitic proxy layers, synthetic fallback branches, and synonymous wrappers "
            "may be collapsed. Real domain logic, safety, observability, and decision discipline may not."
        ),
    ),
    SimplificationRule(
        code="SIMPLIFY-002",
        title="One real logic layer, one thin boundary adapter",
        description=(
            "After simplification the target area should converge toward one layer with real logic and one thin "
            "boundary adapter. Neighboring layers that only relay the same payload must not remain."
        ),
    ),
    SimplificationRule(
        code="SIMPLIFY-003",
        title="Full functionality preservation is mandatory",
        description="Any simplification that reduces project functionality is forbidden.",
    ),
    SimplificationRule(
        code="SIMPLIFY-004",
        title="Architectural entropy is forbidden",
        description=(
            "No new synonymous paths, no new parallel truth-lines, no new temporary helper stacks without an "
            "explicit canonical reason and regression lock."
        ),
    ),
    SimplificationRule(
        code="SIMPLIFY-005",
        title="Parasitic glue logic is forbidden",
        description=(
            "Layers that only rename fields, relay payloads, rebuild the same keys, or add a second fallback "
            "must be collapsed or removed."
        ),
    ),
    SimplificationRule(
        code="SIMPLIFY-006",
        title="Duplicate defensive logic is forbidden",
        description="The same guard or safety check must not live in neighboring layers without a clear reason.",
    ),
    SimplificationRule(
        code="SIMPLIFY-007",
        title="Synonymous logic is forbidden",
        description="If two modules solve the same problem with different names, one must be merged, deleted, or reduced to a thin shim.",
    ),
    SimplificationRule(
        code="SIMPLIFY-008",
        title="False fallback truth is forbidden",
        description="Synthetic identities such as default or legacy must not replace missing real business truth.",
    ),
    SimplificationRule(
        code="SIMPLIFY-009",
        title="Fail-closed beats soft continuation",
        description="When forced to choose, the canon requires fail-closed behavior over hidden synthetic continuation.",
    ),
    SimplificationRule(
        code="SIMPLIFY-010",
        title="DecisionCore bypass is forbidden",
        description="No simplification may open a second decision path or hidden direct-effects path.",
    ),
    SimplificationRule(
        code="SIMPLIFY-011",
        title="Observability loss is forbidden",
        description="No simplification may degrade traceability, replayability, or auditability.",
    ),
    SimplificationRule(
        code="SIMPLIFY-012",
        title="Simplification requires proof",
        description=(
            "A layer may be collapsed only if it is proven not to carry real domain meaning, safety invariants, "
            "or mandatory observability responsibilities."
        ),
    ),
    SimplificationRule(
        code="SIMPLIFY-013",
        title="Compatibility may exist only as a thin shim",
        description="Compatibility layers may remain only as thin pass-through shims without their own fallback semantics.",
    ),
    SimplificationRule(
        code="SIMPLIFY-014",
        title="Map first, cut second",
        description="Before radical simplification each layer must be explicitly classified as keep, merge, or delete.",
    ),
    SimplificationRule(
        code="SIMPLIFY-015",
        title="Public contract regression is forbidden",
        description="No simplification may silently break a public runtime, readmodel, or tested contract.",
    ),
    SimplificationRule(
        code="SIMPLIFY-016",
        title="False improvement is forbidden",
        description=(
            "A change is not an improvement merely because it reduces file count or line count. If it weakens "
            "boundaries, safety, observability, or route discipline, it is forbidden."
        ),
    ),
    SimplificationRule(
        code="SIMPLIFY-017",
        title="Architectural locks must stay distinct",
        description=(
            "Reduce only what does not blur separate architectural locks. Independent canonical-path, decision, "
            "finance, safety, or transition locks must not be collapsed into a mega-lock that weakens signal "
            "localization or hides an alternative path."
        ),
    ),
)

ALL_CANON_INVARIANTS: Final[tuple[CanonInvariant, ...]] = (
    DECISION_DISCIPLINE_INVARIANTS
    + SAFETY_INVARIANTS
    + OBSERVABILITY_INVARIANTS
    + DOMAIN_BOUNDARY_INVARIANTS
)


def iter_all_invariants() -> Iterable[CanonInvariant]:
    return ALL_CANON_INVARIANTS


def iter_all_rules() -> Iterable[SimplificationRule]:
    return SIMPLIFICATION_RULES
