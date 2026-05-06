from pathlib import Path


def test_platform_support_no_shadow_decision_core_class() -> None:
    text = Path("runtime/platform/support/optimization/contracts.py").read_text(encoding="utf-8")
    assert "class DecisionCore" not in text
    assert "CANON_COMPAT_SHIM = True" in text
