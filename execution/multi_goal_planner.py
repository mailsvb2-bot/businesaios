from __future__ import annotations

from application.planning.multi_goal_planner import (
    CANON_MULTI_GOAL_PLANNER as CANON_MULTI_GOAL_PLANNER,
    FileMultiGoalPlannerStore as FileMultiGoalPlannerStore,
    GoalQueueItem as GoalQueueItem,
    MULTI_GOAL_SCHEMA_VERSION as MULTI_GOAL_SCHEMA_VERSION,
    MultiGoalPlanSnapshot as MultiGoalPlanSnapshot,
    MultiGoalPlannerService as MultiGoalPlannerService,
    MultiGoalSelection as MultiGoalSelection,
)

CANON_MULTI_GOAL_PLANNER_COMPAT_SHIM = True
CANON_MULTI_GOAL_PLANNER_FINAL_OWNER = "application.planning.multi_goal_planner"
CANON_MULTI_GOAL_PLANNER_SURFACE = "LongHorizonPlanner"

__all__ = [
    "CANON_MULTI_GOAL_PLANNER",
    "CANON_MULTI_GOAL_PLANNER_COMPAT_SHIM",
    "CANON_MULTI_GOAL_PLANNER_FINAL_OWNER",
    "CANON_MULTI_GOAL_PLANNER_SURFACE",
    "FileMultiGoalPlannerStore",
    "GoalQueueItem",
    "MULTI_GOAL_SCHEMA_VERSION",
    "MultiGoalPlanSnapshot",
    "MultiGoalPlannerService",
    "MultiGoalSelection",
]
