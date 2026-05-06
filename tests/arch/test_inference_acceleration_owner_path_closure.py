from __future__ import annotations

from pathlib import Path


def test_inference_dispatch_uses_canonical_acceleration_owner_path() -> None:
    source = Path("execution/inference_dispatch_orchestrator.py").read_text(encoding="utf-8")
    assert "ProviderAccelerationPressurePolicy" in source
    assert "InferenceAccelerationLog" in source
    assert "InferenceProviderAccelerationProfileCatalog" in source


def test_no_alt_acceleration_summary_surface_outside_runtime_summary() -> None:
    offenders: list[str] = []
    for path in Path("observability").rglob("*.py"):
        if path.name == "inference_runtime_summary.py":
            continue
        text = path.read_text(encoding="utf-8")
        if "acceleration_summary" in text:
            offenders.append(str(path))
    assert offenders == []
