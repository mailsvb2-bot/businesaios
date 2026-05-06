from __future__ import annotations

from pathlib import Path

from canon.collapse_readiness import CORE_RUNTIME_COLLAPSED_SURFACES, CORE_RUNTIME_COLLAPSE_READY_SURFACES

ROOT = Path(__file__).resolve().parents[2]


def _python_files() -> list[Path]:
    return [p for p in ROOT.rglob("*.py") if ".git" not in p.parts and "__pycache__" not in p.parts]


def _module_import_text(module: str) -> tuple[str, str]:
    dotted = module
    return (f"from {dotted} import", f"import {dotted}")


def test_collapse_manifest_tracks_collapsed_and_remaining_heavy_surfaces() -> None:
    assert CORE_RUNTIME_COLLAPSED_SURFACES["runtime.application.action_dispatcher"] == "application.decision.action_dispatcher"
    assert CORE_RUNTIME_COLLAPSED_SURFACES["runtime.application.action_validator"] == "application.decision.action_validator"
    assert CORE_RUNTIME_COLLAPSED_SURFACES["runtime.execution.telemetry"] == "runtime.observability.telemetry"
    assert CORE_RUNTIME_COLLAPSED_SURFACES["core.ai.decision_trace"] == "core.decision.ai_decision_trace"
    assert CORE_RUNTIME_COLLAPSED_SURFACES["runtime.platform.support.serving.runtime.action_validator"] == "application.decision.action_validator"
    assert CORE_RUNTIME_COLLAPSED_SURFACES["attribution.attribution_engine"] == "attribution.catalog"
    assert CORE_RUNTIME_COLLAPSED_SURFACES["flow.execution_to_feedback_flow"] == "orchestration.execution_feedback_bridge"
    assert CORE_RUNTIME_COLLAPSED_SURFACES["orchestration.execution_pipeline"] == "execution.execution_pipeline"
    assert CORE_RUNTIME_COLLAPSED_SURFACES["execution.action_result_store"] == "execution.run_result_store"
    assert CORE_RUNTIME_COLLAPSED_SURFACES["runtime.executor_infra"] == "runtime.execution.executor_state"
    assert CORE_RUNTIME_COLLAPSED_SURFACES["boot.app_boot"] == "bootstrap.app_boot"


def test_project_internal_code_no_longer_imports_collapsed_or_ready_compat_surfaces() -> None:
    violations: list[str] = []
    allowed_prefixes = ("tests/",)
    allowed_owner_files = {
        "boot/runtime_orchestrator.py",
        "bootstrap/compose.py",
        "bootstrap/runtime_integration.py",
        "interfaces/multichannel/__init__.py",
        "runtime/bootstrap.py",
        "runtime/bootstrap/dependency_wiring.py",
        "runtime/bootstrap/sovereign_bootstrap.py",
        "runtime/entrypoints/telegram_longpoll.py",
    }
    compat_needles = {
        compat_module: _module_import_text(compat_module)
        for compat_module in {**CORE_RUNTIME_COLLAPSED_SURFACES, **CORE_RUNTIME_COLLAPSE_READY_SURFACES}
    }
    for path in _python_files():
        rel = path.relative_to(ROOT).as_posix()
        if rel.startswith(allowed_prefixes) or rel in allowed_owner_files:
            continue
        text = path.read_text(encoding="utf-8")
        for compat_module, needles in compat_needles.items():
            if any(needle in text for needle in needles):
                violations.append(f"{rel} -> {compat_module}")
    assert not violations, ("Compat surfaces still used internally:\n" + "\n".join(sorted(violations)))


def test_runtime_application_package_root_is_thin_facade() -> None:
    text = (ROOT / "runtime/application/__init__.py").read_text(encoding="utf-8")
    assert "CANON_RUNTIME_APPLICATION_PACKAGE_OWNER = True" in text
    assert "from application.decision.action_dispatcher import ActionDispatcher" in text
    assert "from runtime.application.contracts import (" in text
    assert '"public_api": "runtime.application.public_api"' in text
    assert "_install_compat_aliases()" in text


def test_core_decision_package_root_routes_to_public_api() -> None:
    text = (ROOT / "core/decision/__init__.py").read_text(encoding="utf-8")
    assert 'CANONICAL_OWNER_DECISION_SURFACE = "application.decision"' in text
    assert "CANON_CORE_DECISION_NAMESPACE = True" in text



def test_boot_runtime_orchestrator_is_marked_collapsed_to_bootstrap_pkg_owner() -> None:
    from canon.collapse_readiness import CORE_RUNTIME_COLLAPSED_SURFACES

    assert CORE_RUNTIME_COLLAPSED_SURFACES["boot.runtime_orchestrator"] == "bootstrap.compose"


def test_boot_runtime_integration_collapse_manifest_points_to_sovereign_owner() -> None:
    from canon.collapse_readiness import CORE_RUNTIME_COLLAPSED_SURFACES

    assert CORE_RUNTIME_COLLAPSED_SURFACES['boot.runtime_integration'] == 'bootstrap.runtime_integration'
