from __future__ import annotations

USER_SCENARIO_TARGETS = (
    "tests/integration/headless/test_cli_capability_matrix.py",
    "tests/integration/headless/test_cli_connector_matrix.py",
    "tests/integration/headless/test_cli_run_smoke.py",
    "tests/integration/headless/test_cli_scenario_smoke.py",
    "tests/integration/headless/test_sdk_execute_smoke.py",
)

USER_SCENARIO_MARK_EXPRESSION = "not slow and not gate"


__all__ = ["USER_SCENARIO_MARK_EXPRESSION", "USER_SCENARIO_TARGETS"]
