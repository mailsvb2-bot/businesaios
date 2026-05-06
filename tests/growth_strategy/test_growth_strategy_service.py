from __future__ import annotations

from pathlib import Path

from runtime.platform.event_store.sqlite_event_store import SqliteEventStore
from core.growth.strategy.service import GrowthStrategyService


def test_generate_backlog_fallback_creates_hypotheses(tmp_path: Path):
    db = tmp_path / "events.db"
    with SqliteEventStore(str(db)) as store:
        svc = GrowthStrategyService(event_store=store, llm=None)
        plan = svc.generate_backlog(tenant_id="t1", user_id="u1", decision_id="d1", correlation_id="c1", n=4)
        assert plan.tenant_id == "t1"
        assert len(plan.top_hypotheses) >= 2

        backlog = svc.backlog(tenant_id="t1", limit=20)
        assert len(backlog) >= 2
        h, s, state = backlog[0]
        assert h.hypothesis_id
        assert state in {"new", "accepted", "rejected", "archived"}
        assert s is None or s.hypothesis_id == h.hypothesis_id


def test_accept_reject_updates_state(tmp_path: Path):
    db = tmp_path / "events.db"
    with SqliteEventStore(str(db)) as store:
        svc = GrowthStrategyService(event_store=store, llm=None)
        plan = svc.generate_backlog(tenant_id="t1", user_id="u1", decision_id="d1", correlation_id="c1", n=3)
        hid = plan.top_hypotheses[0].hypothesis_id

        svc.accept_hypothesis(tenant_id="t1", user_id="u1", decision_id="d2", correlation_id="c2", hypothesis_id=hid)
        backlog = svc.backlog(tenant_id="t1", limit=10)
        states = {h.hypothesis_id: st for (h, _, st) in backlog}
        assert states.get(hid) == "accepted"

        svc.reject_hypothesis(tenant_id="t1", user_id="u1", decision_id="d3", correlation_id="c3", hypothesis_id=hid)
        backlog2 = svc.backlog(tenant_id="t1", limit=10)
        states2 = {h.hypothesis_id: st for (h, _, st) in backlog2}
        assert states2.get(hid) == "rejected"
