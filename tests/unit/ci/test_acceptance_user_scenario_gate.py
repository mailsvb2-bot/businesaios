from __future__ import annotations

import sys
from pathlib import Path

from scripts.ci.plan_registry import allowed_gates, plan_for_gate
from scripts.ci.step_registry import handler_for_step
from scripts.ci.subprocess_io import run_command
from scripts.ci.user_scenario_targets import USER_SCENARIO_MARK_EXPRESSION, USER_SCENARIO_TARGETS, USER_SCENARIOS


def test_acceptance_gate_is_registered_as_user_scenario_gate() -> None:
    assert "acceptance" in allowed_gates()
    assert tuple(step.name for step in plan_for_gate("acceptance").steps) == (
        "assert-project-shape",
        "dependency-lock",
        "doctor-check",
        "user-scenario-gate",
    )
    assert callable(handler_for_step("user-scenario-gate"))


def test_user_scenario_gate_targets_existing_user_surfaces() -> None:
    assert USER_SCENARIO_MARK_EXPRESSION == "not slow and not gate"
    assert USER_SCENARIOS == (
        ("capability_matrix", "tests/integration/headless/test_cli_capability_matrix.py"),
        ("connector_matrix", "tests/integration/headless/test_cli_connector_matrix.py"),
        ("cli_run", "tests/integration/headless/test_cli_run_smoke.py"),
        ("cli_scenario", "tests/integration/headless/test_cli_scenario_smoke.py"),
        ("sdk_execute", "tests/integration/headless/test_sdk_execute_smoke.py"),
        ("api_onboarding_workspace", "tests/integration/http/test_api_onboarding_workspace_e2e.py"),
    )
    assert USER_SCENARIO_TARGETS == tuple(target for _, target in USER_SCENARIOS)
    for target in USER_SCENARIO_TARGETS:
        assert Path(target).exists(), target


def test_windows_acceptance_reuses_canonical_user_scenario_gate() -> None:
    workflow = Path(".github/workflows/ci.yml").read_text(encoding="utf-8")
    windows_job = workflow.split("  windows-acceptance:", 1)[1]
    assert "runs-on: windows-2025" in windows_job
    assert "python -m scripts.ci.cli --gate acceptance" in windows_job
    assert "pytest " not in windows_job
    assert "rust/rust-toolchain.toml" in windows_job
    assert "rustup toolchain install $toolchain --profile minimal --no-self-update" in windows_job
    assert "rustup toolchain install 1.75.0" not in windows_job
    assert "cargo fetch --locked" in windows_job
    assert "CARGO_NET_OFFLINE=true" in windows_job
    assert "vswhere.exe" in windows_job
    assert "Microsoft.VisualStudio.Component.VC.Tools.x86.x64" in windows_job
    assert "vcvars64.bat" in windows_job
    assert "if-no-files-found: error" in windows_job


def test_acceptance_toolchain_policy_crosses_hermetic_subprocess_boundary(monkeypatch) -> None:
    preserved = {
        "CARGO_NET_OFFLINE": "true",
        "SYSTEMROOT": "windows-system-root",
        "USERPROFILE": "windows-user-profile",
        "HOMEDRIVE": "W:",
        "HOMEPATH": "\\Users\\canonical",
        "INCLUDE": "msvc-include-search",
        "LIB": "msvc-lib-search",
        "LIBPATH": "msvc-libpath-search",
    }
    for key, value in preserved.items():
        monkeypatch.setenv(key, value)
    monkeypatch.setenv("BUSINESAIOS_UNTRUSTED_AMBIENT_ENV", "must-not-leak")
    keys = (
        "CARGO_NET_OFFLINE", "SYSTEMROOT", "USERPROFILE", "HOMEDRIVE", "HOMEPATH",
        "INCLUDE", "LIB", "LIBPATH", "BUSINESAIOS_UNTRUSTED_AMBIENT_ENV",
    )
    script = f"import os; print('|'.join(os.getenv(k, '') for k in {keys!r}))"
    outcome = run_command([sys.executable, "-c", script], echo_output=False)
    assert outcome.returncode == 0
    assert outcome.stdout.strip() == (
        "true|windows-system-root|windows-user-profile|W:|\\Users\\canonical|"
        "msvc-include-search|msvc-lib-search|msvc-libpath-search|"
    )
