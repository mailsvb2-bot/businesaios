from __future__ import annotations

USER_SCENARIOS = (
    ("capability_matrix", "tests/integration/headless/test_cli_capability_matrix.py"),
    ("connector_matrix", "tests/integration/headless/test_cli_connector_matrix.py"),
    ("cli_run", "tests/integration/headless/test_cli_run_smoke.py"),
    ("cli_scenario", "tests/integration/headless/test_cli_scenario_smoke.py"),
    ("sdk_execute", "tests/integration/headless/test_sdk_execute_smoke.py"),
    ("api_onboarding_workspace", "tests/integration/http/test_api_onboarding_workspace_e2e.py"),
)
USER_SCENARIO_TARGETS = tuple(target for _, target in USER_SCENARIOS)
USER_SCENARIO_MARK_EXPRESSION = "not slow and not gate"
USER_SCENARIO_EVIDENCE_NAME = "user-scenario-evidence.json"
USER_SCENARIO_RUST_FIXTURE = "safety_fixtures/businessaios_user_scenario_matrix_golden.json"
__all__ = ["USER_SCENARIO_EVIDENCE_NAME", "USER_SCENARIO_MARK_EXPRESSION", "USER_SCENARIO_RUST_FIXTURE", "USER_SCENARIOS", "USER_SCENARIO_TARGETS"]
