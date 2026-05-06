from __future__ import annotations

from pathlib import Path


def test_runtime_observability_routes_runtime_events_via_canonical_audit_owner() -> None:
    source = Path("runtime/runtime_observability.py").read_text(encoding="utf-8")
    assert "def record_audit_event(" in source
    assert 'self.record_audit_event("runtime_trace_story"' in source
    assert 'self.audit_log.append("runtime_trace_story"' not in source
