from __future__ import annotations

import json
from pathlib import Path

from application.business_autonomy.safety_core import build_safety_core_admin_surface
from application.business_autonomy.safety_core_diagnostics import (
    LIVE_CONTRACT_VERSION,
    evaluate_live_contract_case,
    write_safety_core_parity_evidence,
)
from interfaces.api.business_autonomy_route_handlers import build_business_autonomy_route_handlers
from scripts.ci import step_rust_supply_chain


def test_live_contract_fixtures_match_python_safety_evaluator() -> None:
    path = Path("safety_fixtures/businessaios_safety_live_contract_golden.json")
    payload = json.loads(path.read_text(encoding="utf-8"))

    assert payload["version"] == LIVE_CONTRACT_VERSION
    for case in payload["cases"]:
        verdict = evaluate_live_contract_case(case)
        expected = case["expected"]
        assert verdict.allowed is bool(expected["allowed"]), case["name"]
        assert verdict.reason == expected["reason"], case["name"]


def test_safety_core_parity_evidence_artifact_schema(tmp_path) -> None:
    target = tmp_path / "safety_core_parity.json"
    written = write_safety_core_parity_evidence(repo_root=Path.cwd(), output_path=target)
    payload = json.loads(written.read_text(encoding="utf-8"))

    assert payload["artifact"] == "safety_core_parity"
    assert payload["passed"] is True
    assert payload["drift_detected"] is False
    assert payload["golden_fixture_version"] == "businessaios_safety_core_golden.v1"
    assert payload["live_contract_version"] == LIVE_CONTRACT_VERSION
    assert payload["rust_msrv"] == "1.75.0"
    assert payload["rust_edition"] == "2021"
    assert payload["rust_diagnostic_bridge"]["available"] in {True, False}
    assert payload["core_cases"]
    assert payload["live_contract_cases"]


def test_safety_core_admin_surface_exposes_evidence_and_supply_chain() -> None:
    surface = build_safety_core_admin_surface(parity_checked=True, drift_detected=False)

    assert surface["parity_artifact_path"] == "artifacts/ci/safety_core_parity.json"
    assert surface["supply_chain_artifact_path"] == "artifacts/ci/rust_supply_chain.json"
    assert surface["supply_chain_checked"] is True
    assert surface["rust_diagnostic_bridge"] == "cli_only_admin_diagnostics"
    assert surface["live_contract_version"] == LIVE_CONTRACT_VERSION
    assert "write_action" in surface["guards"]
    assert "campaign_scope" in surface["guards"]


def test_route_handlers_expose_safety_evidence_surface() -> None:
    handlers = build_business_autonomy_route_handlers(stack={})
    surface = handlers.get_safety_core_surface()

    assert surface["parity_artifact_path"] == "artifacts/ci/safety_core_parity.json"
    assert surface["supply_chain_artifact_path"] == "artifacts/ci/rust_supply_chain.json"
    assert surface["rust_diagnostic_bridge"] == "cli_only_admin_diagnostics"


def test_rust_supply_chain_step_writes_diagnostic_artifact() -> None:
    ok, message = step_rust_supply_chain.run()
    payload = json.loads(Path("artifacts/ci/rust_supply_chain.json").read_text(encoding="utf-8"))

    assert ok is True, message
    assert payload["artifact"] == "rust_supply_chain"
    assert payload["passed"] is True
    assert payload["msrv"] == "1.75.0"
    assert payload["edition"] == "2021"
    assert payload["direct_dependencies"] == ["serde", "serde_json"]
    assert payload["violations"] == []
