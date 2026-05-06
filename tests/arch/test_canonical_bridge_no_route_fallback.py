from __future__ import annotations

from pathlib import Path


def test_canonical_bridge_does_not_accept_route_fallback() -> None:
    text = Path("demand_decision/canonical_decision_bridge.py").read_text(encoding="utf-8")
    assert "must implement canonical issue() or decide()" in text
    assert "hasattr(self._decision_core, 'route')" not in text
    assert ".route(" not in text
