from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

TARGETS = {
    "runtime.tenancy.public_api": "runtime.tenancy",
    "runtime.governance.public_api": "runtime.governance",
    "runtime.decisioning.public_api": "runtime.decisioning",
    "runtime.ads.public_api": "runtime.ads",
    "runtime.actions.public_api": "runtime.actions",
    "runtime.decision.public_api": "runtime.decision",
    "runtime.world_model.public_api": "runtime.world_model",
    "runtime.observability.public_api": "runtime.observability",
    "runtime.creative.public_api": "runtime.creative",
    "runtime.events.public_api": "runtime.events",
    "runtime.economics.public_api": "runtime.economics",
}

EXCLUDED = {
    "canon/transition_surfaces.py",
    "runtime/canonical_surface_manifest.py",
    "tests/arch/test_runtime_owner_import_collapse_wave157.py",
}


def test_runtime_internal_code_uses_owner_roots_instead_of_public_api_aliases() -> None:
    offenders: list[str] = []
    for path in sorted((ROOT / "runtime").rglob("*.py")):
        rel = path.relative_to(ROOT).as_posix()
        if rel in EXCLUDED:
            continue
        text = path.read_text(encoding="utf-8")
        for compat_surface, owner_surface in TARGETS.items():
            if compat_surface in text:
                offenders.append(f"{rel}: {compat_surface} -> {owner_surface}")
    assert not offenders, "\n".join(offenders)
