from __future__ import annotations

CANON_ANTI_SECOND_BRAIN_RULES = True
CANONICAL_DECISION_CORE_PATH = "core/ai/decision_core.py"

# Names that unambiguously express final decision authority even without a
# receiver. Generic lifecycle verbs such as issue/optimize are contextual so
# certificate, token, numerical, and compiler services keep working.
HARD_DECISION_AUTHORITY_METHODS = frozenset(
    {
        "decide",
        "decide_strategy",
        "emit_final_action",
        "issue_strategy",
        "select_final_action",
    }
)
CONTEXTUAL_DECISION_AUTHORITY_METHODS = frozenset({"issue", "optimize"})
DECISION_AUTHORITY_METHODS = (
    HARD_DECISION_AUTHORITY_METHODS | CONTEXTUAL_DECISION_AUTHORITY_METHODS
)

DECISION_AUTHORITY_TYPE_TOKENS = (
    "decisioncore",
    "decisionengine",
    "plannerengine",
    "secondbrain",
    "shadowbrain",
    "alternatebrain",
    "localbrain",
)

DECISION_AUTHORITY_RECEIVER_TOKENS = (
    "brain",
    "decision",
    "decisioncore",
    "planner",
    "sovereign",
)

# Tests may model negative examples. Production authority is file-exact: adding
# a new module under core/ai or application/decision_runtime never grants it
# permission to issue decisions. Compatibility gateways must delegate to one of
# these owners rather than acquiring an exception of their own.
CANONICAL_DECISION_OWNER_DIR_PREFIXES = ("tests/",)
CANONICAL_DECISION_OWNER_FILES = frozenset(
    {
        CANONICAL_DECISION_CORE_PATH,
        "runtime/decision_gateway.py",
        "runtime/decision_path_lock.py",
    }
)
CANONICAL_DECISION_OWNER_PREFIXES = (
    *CANONICAL_DECISION_OWNER_DIR_PREFIXES,
    *tuple(sorted(CANONICAL_DECISION_OWNER_FILES)),
)


def is_canonical_decision_owner_path(path: str) -> bool:
    normalized = str(path).replace("\\", "/").removeprefix("./")
    return (
        normalized in CANONICAL_DECISION_OWNER_FILES
        or normalized.startswith(CANONICAL_DECISION_OWNER_DIR_PREFIXES)
    )


FORBIDDEN_DECISION_CLASS_NAMES = frozenset(
    {
        "AutonomousBrain",
        "DecisionEngineFacade",
        "GrowthBrain",
        "SecondDecisionCore",
        "StrategyBrain",
    }
)

# Compatibility contract: retain the historical public set exactly. New static
# guards consume DECISION_AUTHORITY_METHODS without changing existing callers.
FORBIDDEN_DECISION_METHODS = {
    "decide_strategy",
    "emit_final_action",
    "issue_strategy",
    "select_final_action",
}
