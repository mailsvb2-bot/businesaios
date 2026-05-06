from __future__ import annotations

from pathlib import Path

from tools.canon_audit.call_graph import CallEdge
from tools.canon_audit.constructor_flow import ConstructorEdge
from tools.canon_audit.entrypoint_shortcut_scan import scan_entrypoint_runtime_shortcuts
from tools.canon_audit.provider_wiring_audit import scan_provider_wiring
from tools.canon_audit.route_resolver import scan_route_expectations


def test_entrypoint_runtime_shortcut_flagged() -> None:
    edges = [
        CallEdge(
            caller_fqname="interfaces.api.routes:execute",
            callee_ref="runtime.execution:RuntimeExecutor",
            file_path=Path("dummy.py"),
            lineno=20,
        )
    ]
    assert any(v.code == "CANON_ENTRYPOINT_RUNTIME_SHORTCUT" for v in scan_entrypoint_runtime_shortcuts(edges))
    assert any(v.code == "CANON_ROUTE_FORBIDDEN_CALL" for v in scan_route_expectations(edges))


def test_provider_wiring_forbidden() -> None:
    edges = [
        ConstructorEdge(
            caller_module="application.decision.service",
            caller_scope="DecisionService.__init__",
            target_ref="runtime._internal:EffectRouter",
            assigned_name="router",
            file_path=Path("dummy.py"),
            lineno=8,
        )
    ]
    assert any(v.code == "CANON_PROVIDER_WIRING_DECISION_RUNTIME" for v in scan_provider_wiring(edges))
