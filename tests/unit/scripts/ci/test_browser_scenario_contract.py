from __future__ import annotations

import json
from pathlib import Path

from scripts.ci import browser_evidence


def test_browser_proof_contract_owns_the_required_scenario() -> None:
    contract = json.loads(Path(browser_evidence.BROWSER_PROJECT_MATRIX).read_text(encoding="utf-8"))
    assert contract["schema"] == browser_evidence.BROWSER_PROJECT_MATRIX_SCHEMA
    assert contract["scenarios"] == [
        {
            "id": "onboarding_owner_workspace",
            "title": "onboarding creates a read-only OWNER workspace without persisting the API key",
            "file": "onboarding-workspace.spec.js",
        }
    ]
    scenario = Path("frontend/e2e/onboarding-workspace.spec.js").read_text(encoding="utf-8")
    assert 'test(canonicalScenario.title' in scenario
    assert 'find((item) => item?.id === "onboarding_owner_workspace")' in scenario


def test_scenario_matrix_rejects_consistent_forged_identity() -> None:
    snapshot = browser_evidence._matrix_snapshot()
    assert snapshot is not None
    projects, canonical, _ = snapshot
    names = tuple(project["name"] for project in projects)
    valid = [(project, canonical[0][0], canonical[0][1]) for project in names]
    forged = [(project, "forged scenario", "forged.spec.js") for project in names]
    assert browser_evidence._scenario_matrix(valid, names, canonical) is not None
    assert browser_evidence._scenario_matrix(forged, names, canonical) is None
