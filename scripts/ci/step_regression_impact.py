from __future__ import annotations

from scripts.ci.plan_registry import plan_for_gate
from scripts.ci.regression_impact_dotfix import blocked_artifact_paths, impacted_rules, missing_fast_steps_for_paths
from scripts.ci.regression_impact_hardened import changed_files
from scripts.ci.step_baseline_contract import run as run_baseline_contract


def run() -> tuple[bool, str]:
    paths = changed_files()
    if not paths:
        return False, "regression impact has no changed files"
    artifacts = blocked_artifact_paths(paths)
    if artifacts:
        return False, "generated/runtime artifacts in change set: " + ", ".join(artifacts[:20])
    fast_steps = tuple(step.name for step in plan_for_gate("fast").steps)
    missing = missing_fast_steps_for_paths(paths, fast_steps)
    if missing:
        impacted = ", ".join(rule.name for rule in impacted_rules(paths)) or "none"
        return False, f"regression impact missing fast step(s): {missing}; impacted={impacted}"
    baseline_ok, baseline_message = run_baseline_contract()
    if not baseline_ok:
        return False, baseline_message
    impacted = tuple(rule.name for rule in impacted_rules(paths))
    if not impacted:
        return True, f"regression impact passed: {len(paths)} changed path(s), no critical domain impact; {baseline_message}"
    return True, f"regression impact passed: impacted={impacted}; changed_paths={len(paths)}; {baseline_message}"


__all__ = ["run"]
