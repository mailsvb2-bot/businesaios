from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _runtime_python_files() -> list[Path]:
    return [p for p in (ROOT / "runtime").rglob("*.py")]


def test_runtime_tenancy_scope_and_tenant_helpers_use_public_surface() -> None:
    offenders: list[str] = []
    for path in _runtime_python_files():
        if path.as_posix().endswith(("runtime/tenancy/__init__.py", "runtime/tenancy/__init__.py")):
            continue
        text = path.read_text(encoding="utf-8")
        if "core.tenancy.scope" in text or "core.tenancy.tenant" in text:
            offenders.append(path.relative_to(ROOT).as_posix())
    assert offenders == []


def test_runtime_proof_registry_uses_public_surface() -> None:
    offenders: list[str] = []
    for path in _runtime_python_files():
        if path.as_posix().endswith(("runtime/proofs/_surface.py", "runtime/proofs/__init__.py")):
            continue
        text = path.read_text(encoding="utf-8")
        if "core.actions.proof_registry" in text:
            offenders.append(path.relative_to(ROOT).as_posix())
    assert offenders == []


def test_runtime_world_model_metadata_uses_public_surface() -> None:
    offenders: list[str] = []
    for path in _runtime_python_files():
        if path.as_posix().endswith(("runtime/world_model/__init__.py", "runtime/world_model/__init__.py")):
            continue
        text = path.read_text(encoding="utf-8")
        if "application.decision_state.world_model_metadata" in text:
            offenders.append(path.relative_to(ROOT).as_posix())
    assert offenders == []


def test_runtime_safety_controls_use_public_surface() -> None:
    offenders: list[str] = []
    for path in _runtime_python_files():
        if path.as_posix().endswith(("runtime/safety/_surface.py", "runtime/safety/__init__.py")):
            continue
        text = path.read_text(encoding="utf-8")
        if "core.safety.controls." in text:
            offenders.append(path.relative_to(ROOT).as_posix())
    assert offenders == []


def test_runtime_boundary_public_surfaces_export_expected_symbols() -> None:
    from runtime.proofs import ACTION_PROOF_EVENT
    from runtime.proofs.contract import PROOF_REGISTRY_CANON, RUNTIME_PROOFS_PUBLIC_API
    from runtime.safety import (
        ControlDecision,
        ControlStatus,
        SafetyActionContext,
        SafetyControlProfile,
        SafetyControlService,
        build_default_profile,
    )
    from runtime.safety.contract import RUNTIME_SAFETY_PUBLIC_API, SAFETY_CONTROLS_CANON
    from runtime.tenancy import TenantId, TenantScope, as_tenant_id, current_tenant_id
    from runtime.world_model import (
        extract_pinned_world_model_meta_from_payload,
        extract_world_model_metadata,
    )

    assert RUNTIME_PROOFS_PUBLIC_API is True
    assert PROOF_REGISTRY_CANON == "runtime.proofs"
    assert ACTION_PROOF_EVENT["noop@v1"] == "decision_executed"
    assert RUNTIME_SAFETY_PUBLIC_API is True
    assert SAFETY_CONTROLS_CANON == "runtime.safety"
    assert SafetyActionContext is not None
    assert ControlDecision is not None
    assert ControlStatus is not None
    assert SafetyControlProfile is not None
    assert SafetyControlService is not None
    assert callable(build_default_profile)
    assert str(as_tenant_id(" tenant-a ")) == "tenant-a"
    scope = TenantScope("tenant-b")
    assert scope.tenant_id == "tenant-b"
    assert TenantId is not None
    assert callable(current_tenant_id)
    assert extract_pinned_world_model_meta_from_payload({"world_model_meta": {"k": "v"}}) == {"k": "v"}
    state = type("S", (), {"meta": {"world_model": "wm"}, "economy": {}})()
    assert extract_world_model_metadata(state=state)["world_model"] == "wm"
