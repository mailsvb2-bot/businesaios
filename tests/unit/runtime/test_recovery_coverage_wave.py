"""Coverage contract for runtime recovery fail-closed behavior."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

import runtime.recovery as recovery


class Archive:
    def __init__(self, items):
        self.items = dict(items)

    def get(self, decision_id):
        return self.items.get(decision_id)


def env(decision_id="d1", tenant_id="tenant-a"):
    return SimpleNamespace(
        decision=SimpleNamespace(
            decision_id=decision_id,
            payload={"tenant_id": tenant_id},
            correlation_id=decision_id,
        ),
        metadata={},
    )


def test_recoverable_item_contract_fallbacks():
    assert tuple(recovery._iter_recoverable_items(outbox=None, limit=1)) == ()
    assert tuple(recovery._iter_recoverable_items(outbox=object(), limit=0)) == ()

    all_box = SimpleNamespace(
        list_claimable_all=lambda *, limit: [SimpleNamespace(message_id="a")]
    )
    assert tuple(recovery._iter_recoverable_items(outbox=all_box, limit=1))[0]["decision_id"] == "a"

    class Legacy:
        def list_claimable(self, *args, **kwargs):
            if "tenant_id" not in kwargs:
                raise TypeError("legacy")
            return [{"id": "b"}]

    assert tuple(recovery._iter_recoverable_items(outbox=Legacy(), limit=1))[0]["id"] == "b"
    pending = SimpleNamespace(list_pending=lambda *, limit: [None])
    assert tuple(recovery._iter_recoverable_items(outbox=pending, limit=1)) == ({},)


def test_identity_and_tenant_fallbacks(monkeypatch):
    assert recovery._decision_id_from_item({"id": " x "}) == "x"
    assert recovery._item_tenant_id({"tenant_id": " "}) == "default"
    monkeypatch.setattr(recovery, "_decision_tenant_id", lambda decision: "decision-tenant")
    assert recovery._env_tenant_id(env=env(), item={"tenant_id": "item-tenant"}) == "decision-tenant"
    monkeypatch.setattr(
        recovery,
        "_decision_tenant_id",
        lambda decision: (_ for _ in ()).throw(RuntimeError()),
    )
    assert recovery._env_tenant_id(env=env(), item={"tenant_id": "item-tenant"}) == "item-tenant"
    assert recovery._resolve_recovery_tenant_id(
        env=SimpleNamespace(decision=None, metadata={"tenant_id": "meta-tenant"}),
        item={},
    ) == "meta-tenant"
    assert recovery._resolve_recovery_tenant_id(
        env=SimpleNamespace(decision=None, metadata={}), item={}
    ) is None


def test_claim_reuses_delivering_and_fails_closed(monkeypatch):
    monkeypatch.setattr(
        recovery,
        "get_delivery_info",
        lambda *args, **kwargs: {"status": "delivering"},
    )
    assert recovery._ensure_claim_or_skip(
        outbox=object(),
        item={"decision_id": "d1", "tenant_id": "t1", "state": "delivering"},
    )
    monkeypatch.setattr(recovery, "get_delivery_info", lambda *args, **kwargs: None)
    monkeypatch.setattr(recovery, "claim_or_skip", lambda *args, **kwargs: True)
    assert recovery._ensure_claim_or_skip(outbox=object(), item={"decision_id": "d1"})
    monkeypatch.setattr(
        recovery,
        "claim_or_skip",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError()),
    )
    assert not recovery._ensure_claim_or_skip(outbox=object(), item={"decision_id": "d1"})
    assert not recovery._ensure_claim_or_skip(outbox=object(), item={})


@pytest.mark.parametrize(
    ("action", "effect"),
    [
        ("quarantine", "quarantine"),
        ("dead_letter", "quarantine"),
        ("skip", "finalize"),
        ("noop", "finalize"),
        ("wait", None),
        ("unknown", "quarantine"),
        ("retry", False),
        ("", False),
    ],
)
def test_recovery_action_matrix(monkeypatch, action, effect):
    calls = []
    monkeypatch.setattr(
        recovery, "_quarantine_item", lambda **kw: calls.append("quarantine")
    )
    monkeypatch.setattr(
        recovery, "_finalize_terminal_skip", lambda **kw: calls.append("finalize")
    )
    handled = recovery._handle_non_resume_action(
        action=action, outbox=object(), env=env(), item={"decision_id": "d1"}
    )
    if effect is False:
        assert handled is False and calls == []
    else:
        assert handled is True
        assert calls == ([] if effect is None else [effect])


def test_recover_pending_executes_only_claimed_resume(monkeypatch):
    items = [
        {},
        {"decision_id": "missing"},
        {"decision_id": "wait"},
        {"decision_id": "resume"},
        {"decision_id": "unclaimed"},
    ]
    outbox = SimpleNamespace(list_claimable_all=lambda *, limit: items)
    archive = Archive(
        {
            "wait": env("wait"),
            "resume": env("resume"),
            "unclaimed": env("unclaimed"),
        }
    )
    executor = SimpleNamespace(execute_recovery=lambda item: executed.append(item))
    executed = []
    quarantined = []
    monkeypatch.setattr(
        recovery, "_quarantine_item", lambda **kw: quarantined.append(kw["reason"])
    )
    monkeypatch.setattr(
        recovery,
        "_resolve_recovery_action",
        lambda *, executor, env: "wait" if env.decision.decision_id == "wait" else "retry",
    )
    monkeypatch.setattr(
        recovery,
        "_ensure_claim_or_skip",
        lambda *, outbox, item: item["decision_id"] == "resume",
    )
    assert recovery.recover_pending(
        executor=executor, outbox=outbox, archive=archive, limit=10
    ) == 1
    assert [item.decision.decision_id for item in executed] == ["resume"]
    assert quarantined == ["missing_archive_envelope"]


def test_execution_failures_are_quarantined(monkeypatch):
    calls = []
    logs = []
    monkeypatch.setattr(
        recovery, "_quarantine_item", lambda **kw: calls.append(kw["reason"])
    )
    monkeypatch.setattr(
        recovery,
        "log_exception_throttled",
        lambda *args, **kw: logs.append(kw["key"]),
    )
    expired = type("DecisionExpired", (RuntimeError,), {})("expired")
    recovery._handle_recovery_execution_failure(
        outbox=object(), env=env(), item={"decision_id": "d1"}, exc=expired
    )
    assert calls == ["DecisionExpired"]
    calls.clear()
    recovery._handle_recovery_execution_failure(
        outbox=object(),
        env=SimpleNamespace(decision=None, metadata={}),
        item={"decision_id": "d2", "tenant_id": ""},
        exc=RuntimeError("boom"),
    )
    assert calls == ["missing_recovery_tenant:RuntimeError"]
    assert "recovery.execute_recovery.missing_tenant" in logs


def test_plan_and_terminal_helpers_fail_closed(monkeypatch):
    executor = SimpleNamespace(
        _reliability=SimpleNamespace(
            plan=lambda item: (_ for _ in ()).throw(RuntimeError())
        )
    )
    assert recovery._recovery_plan(executor=executor, env=object()) is None
    assert recovery._plan_action(None) == ""
    warnings = []
    monkeypatch.setattr(
        recovery, "_warn_recovery_issue", lambda **kw: warnings.append(kw["key"])
    )
    monkeypatch.setattr(
        recovery,
        "quarantine_recovery_outcome",
        lambda **kw: (_ for _ in ()).throw(RuntimeError()),
    )
    monkeypatch.setattr(
        recovery,
        "finalize_terminal_recovery_outcome",
        lambda **kw: (_ for _ in ()).throw(RuntimeError()),
    )
    recovery._quarantine_item(
        outbox=object(), env=SimpleNamespace(decision=None), item={"decision_id": "d1"}, reason="x"
    )
    recovery._finalize_terminal_skip(
        outbox=object(), env=SimpleNamespace(decision=None), item={"decision_id": "d2"}, reason="y"
    )
    assert warnings == ["recovery.dead_letter.move", "recovery.terminal_skip.finalize"]
