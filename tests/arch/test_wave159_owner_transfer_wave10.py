from __future__ import annotations

import importlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_wave10_boot_support_cluster_has_final_owners() -> None:
    for rel in (
        "bootstrap/assembly_runtime.py",
        "bootstrap/boot_helpers.py",
        "bootstrap/boot_observability.py",
        "bootstrap/boot_phases.py",
        "bootstrap/entrypoint_context.py",
        "bootstrap/finalize_runtime_args.py",
        "bootstrap/handlers_wiring.py",
        "bootstrap/health_server.py",
        "bootstrap/logging_setup.py",
        "bootstrap/mode_gate.py",
        "bootstrap/registration_manifest.py",
        "bootstrap/route_surface.py",
        "bootstrap/self_check.py",
    ):
        assert (ROOT / rel).exists(), rel


def test_wave10_runtime_boot_support_cluster_is_package_owned_alias_surface() -> None:
    mapping = {
        "assembly_runtime": "bootstrap.assembly_runtime",
        "boot_helpers": "bootstrap.boot_helpers",
        "boot_observability": "bootstrap.boot_observability",
        "boot_phases": "bootstrap.boot_phases",
        "entrypoint_context": "bootstrap.entrypoint_context",
        "finalize_runtime_args": "bootstrap.finalize_runtime_args",
        "handlers_wiring": "bootstrap.handlers_wiring",
        "health_server": "bootstrap.health_server",
        "logging_setup": "bootstrap.logging_setup",
        "mode_gate": "bootstrap.mode_gate",
        "registration_manifest": "bootstrap.registration_manifest",
        "route_surface": "bootstrap.route_surface",
        "self_check": "bootstrap.self_check",
    }
    owner_root = (ROOT / "runtime/boot/__init__.py").read_text(encoding="utf-8")
    assert "_COMPAT_MODULE_ALIAS_MAP" in owner_root
    for alias_name, owner in mapping.items():
        assert not (ROOT / f"runtime/boot/{alias_name}.py").exists()
        compat = importlib.import_module(f"runtime.boot.{alias_name}")
        assert hasattr(compat, "__getattr__") or compat is importlib.import_module(owner)


def test_wave10_execute_action_stack_and_error_presenter_move_to_entrypoints() -> None:
    stack = importlib.import_module("interfaces.api.execute_action_api_stack")
    presenter = importlib.import_module("interfaces.api.error_presenter")
    assert hasattr(stack, "build_execute_action_stack_bundle")
    assert hasattr(presenter, "present_api_error")
