from __future__ import annotations

from application.planning.goal_plan_memory import (
    CANON_GOAL_PLAN_MEMORY,
    FileGoalPlanMemoryStore,
    GOAL_PLAN_SCHEMA_VERSION,
    GoalPlanMemoryService,
    GoalPlanSnapshot,
    GoalPlanStepRecord,
)

CANON_GOAL_PLAN_MEMORY_COMPAT_SHIM = True
CANON_GOAL_PLAN_MEMORY_FINAL_OWNER = "application.planning.goal_plan_memory"
