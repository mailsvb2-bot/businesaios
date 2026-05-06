from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_core_policy_exports_runtime_rollout_components() -> None:
    text = _read("core/policies/__init__.py")
    required = (
        "PolicyRegistry",
        "CanaryRouter",
        "SafetyEvaluator",
        "SafeRolloutManager",
        "OfflineTrainer",
    )
    missing = [name for name in required if name not in text]
    assert missing == [], missing


def test_core_policies_package_declares_concrete_policy_boundary() -> None:
    text = _read("core/policies/__init__.py")
    assert "Concrete policies" in text
    assert "never execute effects" in text
