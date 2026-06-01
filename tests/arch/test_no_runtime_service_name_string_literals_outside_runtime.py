from __future__ import annotations

from pathlib import Path

from canon.runtime_string_literal_rules import FORBIDDEN_RUNTIME_SERVICE_NAME_LITERALS

PROJECT_ROOT = Path(__file__).resolve().parents[2]
ALLOWED_PATH_FRAGMENTS = (
    "runtime/service_names.py",
    "canon/",
    "boot/runtime_boot_manifest.py",
    "tests/",
    # Legacy project modules that legitimately carry service labels.
    "core/ads/apply_engine.py",
    "core/ai/decision_runtime.py",
    "application/decision_runtime/emission.py",
    "application/decision_runtime/gate.py",
    "application/decision_runtime/runtime.py",
    "application/headless/decision_gateway.py",
    "bootstrap/bootstrap_config_surface.py",
    "bootstrap/runtime_service_specs.py",
    "execution/budget_guard.py",
    "execution/spend_limit_policy.py",
    "observability/audit_export_service.py",
    "observability/public_api.py",
    "runtime/canonical_surface_manifest.py",
    "runtime/decision_path_lock.py",
    "runtime/platform/support/safety/guards/__init__.py",
    "core/safety/controls/action_budget/guard.py",
    "core/safety/controls/kill_switch/guard.py",
    "core/safety/controls/reward_guard/guard.py",
    "core/safety/controls/simulation_gate/service.py",
    "products/organization_platform/contract.py",
    "runtime/guard_helpers.py",
    "runtime/boot/product_system_builder.py",
    "runtime/boot/system_builder_parts/runtime_services.py",
    "runtime/modules/builtin_modules.py",
    "scripts/check_world_snapshot_no_second_brain.py",
)


def test_no_runtime_service_name_string_literals_outside_runtime() -> None:
    violations: list[str] = []

    for path in PROJECT_ROOT.rglob("*.py"):
        normalized = path.as_posix()

        if any(fragment in normalized for fragment in ALLOWED_PATH_FRAGMENTS):
            continue

        text = path.read_text(encoding="utf-8")

        for literal in FORBIDDEN_RUNTIME_SERVICE_NAME_LITERALS:
            quoted_variants = (
                f'"{literal}"',
                f"'{literal}'",
            )
            if any(variant in text for variant in quoted_variants):
                violations.append(
                    f"{normalized}: contains forbidden runtime service-name literal '{literal}'"
                )

    assert not violations, "\n".join(violations)
