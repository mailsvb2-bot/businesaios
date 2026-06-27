from __future__ import annotations

from scripts.ci.baseline_contract import BASELINE_REQUIREMENTS, baseline_scenario_refs, missing_scenario_paths
from scripts.ci.subprocess_io import run_pytest


def run() -> tuple[bool, str]:
    if not BASELINE_REQUIREMENTS:
        return False, "baseline contract matrix is empty"

    ids = [item.requirement_id for item in BASELINE_REQUIREMENTS]
    duplicates = sorted({item for item in ids if ids.count(item) > 1})
    if duplicates:
        return False, "duplicate baseline requirement ids: " + ", ".join(duplicates)

    missing_paths = missing_scenario_paths()
    if missing_paths:
        return False, "baseline scenario path(s) missing: " + ", ".join(missing_paths[:20])

    scenario_refs = baseline_scenario_refs()
    outcome = run_pytest(["-m", "pytest", *scenario_refs, "-q"], timeout=120)
    if outcome.returncode != 0:
        output = "\n".join(line for line in (outcome.stdout + "\n" + outcome.stderr).splitlines() if line.strip())
        return False, "baseline scenario failure: " + output[:1000]

    return True, f"baseline contract matrix passed: {len(BASELINE_REQUIREMENTS)} requirement(s)"


__all__ = ["run"]
