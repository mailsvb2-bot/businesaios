from __future__ import annotations

from demand_guardrails.rollback_guard import RollbackGuard

def test_routing_rollback_on_bad_outcomes():
    assert RollbackGuard().check(0.8) is True
    assert RollbackGuard().check(0.1) is False
