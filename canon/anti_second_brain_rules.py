from __future__ import annotations

CANON_ANTI_SECOND_BRAIN_RULES = True
CANONICAL_DECISION_CORE_PATH = "core/ai/decision_core.py"

HARD_DECISION_AUTHORITY_METHODS = frozenset(
    {
        "decide",
        "decide_strategy",
        "emit_final_action",
        "issue",
        "issue_strategy",
        "select_final_action",
    }
)
CONTEXTUAL_DECISION_AUTHORITY_METHODS = frozenset({"optimize"})
DECISION_AUTHORITY_METHODS = HARD_DECISION_AUTHORITY_METHODS | CONTEXTUAL_DECISION_AUTHORITY_METHODS

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
)

CANONICAL_DECISION_OWNER_PREFIXES = (
    "core/ai/",
    "application/decision_runtime/",
    "runtime/decision_gateway.py",
    "runtime/decision_path_lock.py",
    "tests/",
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
FORBIDDEN_DECISION_METHODS = set(DECISION_AUTHORITY_METHODS)
