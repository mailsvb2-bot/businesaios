from __future__ import annotations

import pathlib


LEGACY = {
    "runtime_execution.py",
    "state_and_envelope.py",
}

FORBIDDEN_ROOT = {
    "runtime_execution.py",
    "examples/policy_loop_demo.py",
    "state_and_envelope.py",
    "capital_allocation_engine.py",
}


ALLOWED_PATHS = {
    # The learning subsystem legitimately has a policy loop module.
        # Legacy entrypoints are allowed only under experimental/legacy_runtime.
    "experimental/legacy_runtime/policy_loop.py",
}


def test_legacy_entrypoints_not_in_prod_tree():
    """Legacy/demo entrypoints must not exist outside experimental/legacy_runtime."""
    root = pathlib.Path(__file__).resolve().parents[1]
    offenders: list[str] = []

    root_present = {p.name for p in root.glob("*.py")}
    forbidden_root = sorted(root_present & FORBIDDEN_ROOT)
    assert not forbidden_root, (
        "Forbidden legacy entrypoints/modules present in repo root: "
        f"{forbidden_root}"
    )

    for p in root.rglob("*.py"):
        if p.name not in LEGACY and p.name != "policy_loop.py":
            continue
        rel = p.relative_to(root)
        rel_s = str(rel)
        if rel_s in ALLOWED_PATHS:
            continue
        if p.name == "policy_loop.py":
            # Only allowed paths above.
            offenders.append(rel_s)
            continue
        if not (rel.parts and rel.parts[0] == "experimental" and "legacy_runtime" in rel.parts):
            offenders.append(rel_s)

    assert not offenders, "Legacy entrypoints found outside experimental/legacy_runtime:\n" + "\n".join(offenders)
