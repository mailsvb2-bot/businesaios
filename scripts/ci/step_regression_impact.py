from __future__ import annotations

from scripts.ci.plan_registry import plan_for_gate
from scripts.ci.regression_impact_dotfix import blocked_artifact_paths, changed_files, impacted_rules, missing_fast_steps_for_paths


def run() -> tuple[bool, str]:
    paths = changed_files()
    if not paths:
        return False, "regression impact could not determine changed files"

    artifacts = blocked_artifact_paths(paths)
    if artifacts:
        return False, "generated/runtime artifacts in change set: " + ", ".join(artifacts[:20])

    fast_steps = tuple(step.name for step in plan_for_gate("fast").steps)
    missing = missing_fast_steps_for_paths(paths, fast_steps)
    if missing:
        impacted = ", ".join(rule.name for rule in impacted_rules(paths)) or "none"
        return False, f"regression impact missing fast step(s): {missing}; impacted={impacted}"

    impacted = tuple(rule.name for rule in impacted_rules(paths))
    if not impacted:
        return True, f"regression impact passed: {len(paths)} changed path(s), no critical domain impact"
    return True, f"regression impact passed: impacted={impacted}; changed_paths={len(paths)}"


__all__ = ["run"]
