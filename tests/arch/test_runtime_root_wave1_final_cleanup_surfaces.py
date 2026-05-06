from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

SURFACES = {
    "runtime/readiness.py": {
        "required_markers": [
            "CANON_RUNTIME_READINESS_OWNER = True",
            "CANON_RUNTIME_READINESS_STATE_ONLY = True",
            "CANON_RUNTIME_READINESS_NO_DECISION_LOGIC = True",
        ],
        "forbidden_imports": {"boot", "runtime.executor", "decision_core", "boot.factories"},
        "forbidden_tokens": ["compose_runtime(", "bootstrap_runtime(", ".issue(", "register_service(", "register_component("],
    },
    "runtime/wiring.py": {
        "required_markers": [
            "CANON_RUNTIME_WIRING_OWNER = True",
            "CANON_RUNTIME_WIRING_STORAGE_ONLY = True",
            "CANON_RUNTIME_WIRING_NO_DECISION_LOGIC = True",
            "CANON_RUNTIME_WIRING_NO_ROOT_REGISTRY = True",
        ],
        "forbidden_imports": {"runtime.executor", "decision_core", "boot.factories", "shared.registry"},
        "forbidden_tokens": ["compose_runtime(", "bootstrap_runtime(", ".issue(", "RuntimeRegistry(", "ServiceRegistry(", "ComponentRegistry("],
    },
    "runtime/runtime_infra.py": {
        "required_markers": [
            "CANON_RUNTIME_INFRA_CONTRACT = True",
            "CANON_RUNTIME_INFRA_DATA_ONLY = True",
            "CANON_RUNTIME_INFRA_NO_DECISION_LOGIC = True",
        ],
        "forbidden_imports": {"boot", "runtime.executor", "decision_core", "shared.registry"},
        "forbidden_tokens": ["compose_runtime(", "bootstrap_runtime(", ".issue(", "register_service(", "register_component("],
    },
    "runtime/runtime_observability.py": {
        "required_markers": [
            "CANON_RUNTIME_OBSERVABILITY_OWNER = True",
            "CANON_RUNTIME_OBSERVABILITY_AUDIT_ONLY = True",
            "CANON_RUNTIME_OBSERVABILITY_NO_DECISION_LOGIC = True",
        ],
        "forbidden_imports": {"boot", "runtime.executor", "decision_core", "boot.factories"},
        "forbidden_tokens": ["compose_runtime(", "bootstrap_runtime(", ".issue(", "execute(", "dispatch_effect("],
    },
}


def _imports(relative: str) -> set[str]:
    tree = ast.parse((ROOT / relative).read_text(encoding="utf-8"))
    values: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            values.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            values.add("." * node.level + (node.module or ""))
    return values



def test_runtime_wave1_final_cleanup_surfaces_have_owner_markers_and_no_alt_paths() -> None:
    for relative, expectations in SURFACES.items():
        text = (ROOT / relative).read_text(encoding="utf-8")
        for marker in expectations["required_markers"]:
            assert marker in text, f"{relative} missing marker {marker}"
        for token in expectations["forbidden_tokens"]:
            assert token not in text, f"{relative} must not contain {token}"



def test_runtime_wave1_final_cleanup_surfaces_keep_forbidden_imports_out() -> None:
    for relative, expectations in SURFACES.items():
        imports = _imports(relative)
        for bad in expectations["forbidden_imports"]:
            assert all(not (imported == bad or imported.startswith(f"{bad}.")) for imported in imports), f"{relative} must not import {bad}; got {sorted(imports)}"
