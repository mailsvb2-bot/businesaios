from __future__ import annotations
CANON_BOOT_SELF_CHECK_FINAL_OWNER = True

CANON_BOOT_WIRING_ONLY = True


from importlib import import_module


def boot_self_check() -> None:
    """Minimal invariants that must never regress silently."""

    module = import_module("core.decision_core")
    decision_core_cls = getattr(module, "DecisionCore", None)
    assert decision_core_cls is not None, "DecisionCore class must exist"
    assert hasattr(decision_core_cls, "decide"), "DecisionCore must expose decide()"
    assert hasattr(decision_core_cls, "issue"), "DecisionCore must expose issue()"
