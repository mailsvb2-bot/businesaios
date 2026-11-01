"""Bounded canonical Telegram replies without changing action-budget protections."""
from __future__ import annotations

import sqlite3
from types import SimpleNamespace

from core.safety.controls.action_budget.guard import ActionBudgetGuard
from core.safety.controls.action_budget.ledger import InMemoryActionBudgetLedger
from core.safety.controls.action_budget.models import ActionBudget, is_routine_reply
from core.safety.controls.action_context import SafetyActionContext
from core.safety.controls.control_result import ControlStatus
from runtime.platform.safety_action_budget_ledger import PlatformSqliteActionBudgetLedger
from runtime import safety_controls


def _ctx(action="send_message@v1", **payload):
    return SafetyActionContext(action=action, tenant_id="tenant-live", user_id="user-1",
                               payload={"user_id": "user-1", **payload})


def test_reply_does_not_consume_exhausted_lifetime_business_budget(monkeypatch):
    ledger = InMemoryActionBudgetLedger()
    for _ in range(3):
        ledger.record("tenant-live", estimated_cost=2.0)
    guard = ActionBudgetGuard(ledger, ActionBudget(max_cost=5.0, max_actions=2))
    assert guard.evaluate(_ctx()).status == ControlStatus.ALLOW
    assert guard.evaluate(_ctx("capture_payment")).reason == "action_budget_exceeded"
    assert guard.evaluate(_ctx(estimated_cost=1)).reason == "action_budget_exceeded"
    for _ in range(2):
        ledger.record_routine_reply("tenant-live")
    decision = guard.evaluate(_ctx())
    assert decision.status == ControlStatus.BLOCK
    assert decision.reason == "action_budget_exceeded"
    assert decision.details["budget_class"] == "routine_reply_utc_day"
    assert ledger.snapshot("tenant-live") == (6.0, 3)
    assert not is_routine_reply("send_marketing_offer", {})
    assert not is_routine_reply("send_message@v1", {"estimated_cost": 3})


def test_persistent_migration_preserves_financial_totals_and_reply_quota(tmp_path, monkeypatch):
    import runtime.platform.safety_action_budget_ledger as db_module
    database = tmp_path / "safety.sqlite"
    with sqlite3.connect(database) as db:
        db.execute("CREATE TABLE safety_schema_version (component TEXT PRIMARY KEY, version INTEGER NOT NULL)")
        db.execute("INSERT INTO safety_schema_version VALUES ('action_budget_ledger', 2)")
        db.execute("CREATE TABLE safety_action_budget_ledger (tenant_id TEXT PRIMARY KEY, total_cost REAL NOT NULL, total_actions INTEGER NOT NULL, updated_at TEXT NOT NULL DEFAULT '')")
        db.execute("INSERT INTO safety_action_budget_ledger VALUES ('tenant-live', 4000, 1200, '')")
    monkeypatch.setattr(db_module, "routine_reply_day", lambda: "2026-11-01")
    ledger = PlatformSqliteActionBudgetLedger(sqlite_path=str(database))
    assert ledger.snapshot("tenant-live") == (4000.0, 1200)
    assert ledger.routine_reply_count("tenant-live") == 0
    ledger.record_routine_reply("tenant-live")
    ledger.record_routine_reply("tenant-live")
    assert PlatformSqliteActionBudgetLedger(sqlite_path=str(database)).routine_reply_count("tenant-live") == 2
    assert ledger.snapshot("tenant-live") == (4000.0, 1200)
    monkeypatch.setattr(db_module, "routine_reply_day", lambda: "2026-11-02")
    assert ledger.routine_reply_count("tenant-live") == 0


def test_canonical_safety_accountant_records_only_reply_bucket(monkeypatch):
    ledger = InMemoryActionBudgetLedger()
    profile = SimpleNamespace(action_budget_ledger=ledger,
                              action_catalog=SimpleNamespace(resolve=lambda action: None))
    monkeypatch.setattr(safety_controls, "build_safety_control_runtime",
                        lambda: SimpleNamespace(profile=profile))
    monkeypatch.setattr(safety_controls, "_record_safety_event", lambda **kwargs: True)
    safety_controls.record_allowed_action(
        action="send_message@v1", payload={"tenant_id": "tenant-live", "user_id": "user-1"})
    assert ledger.routine_reply_count("tenant-live") == 1
    assert ledger.snapshot("tenant-live") == (0.0, 0)
    safety_controls.record_allowed_action(
        action="send_message@v1", payload={"tenant_id": "tenant-live", "estimated_cost": 1})
    assert ledger.snapshot("tenant-live") == (1.0, 1)
