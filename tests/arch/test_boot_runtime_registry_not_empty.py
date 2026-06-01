from __future__ import annotations

from pathlib import Path

from runtime.runtime_boot import boot_runtime

CANON_BOOT_WIRING_ONLY = True
PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_boot_runtime_registry_not_empty() -> None:
    assert (PROJECT_ROOT / "runtime" / "runtime_boot.py").exists()
    registry = boot_runtime()
    snapshot = registry.snapshot()
    names = getattr(snapshot, "service_names", ())
    assert tuple(names), "boot_runtime() produced an empty runtime registry"
