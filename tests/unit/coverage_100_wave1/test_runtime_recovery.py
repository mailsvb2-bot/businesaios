from __future__ import annotations

from types import SimpleNamespace

import pytest

import runtime.recovery as recovery


class _Archive:
    def __init__(self, values: dict[str, object]) -> None:
        self.values = values
        self.calls: list[str] = []

    def get(self, decision_id: str):
        self.calls.append(decision_id)
        return self.values.get(decision_id)


class _Executor:
    def __init__(self, *, action: str = "resume", failure: Exception | None = None, plan_failure: bool = False) -> None:
        self.failure = failure
        self.executed: list[object] = []
        if plan_failure:
            self._reliability = SimpleNamespace(plan=lambda env: (_ for _ in ()).throw(RuntimeError("plan")))
        else:
            self._reliability = SimpleNamespace(plan=lambda env: SimpleNamespace(recovery_action=action))

    def execute_recovery(self, env: object) -> None:
        self.executed.append(env)
        if self.failure is not None:
            raise self.failure


class _State:
    value = "pending"


class _Item:
    message_id = "message-1"
    decision_id = "decision-1"
    tenant_id = "tenant-a"
    state = _State()
    delivery_attempts = 2
    available_at = 123


def _env(*, decision_id: str = "decision-1", tenant_id: str | None = "tenant-a", metadata=None):
    payload = {} if tenant_id is None else {"tenant_id": tenant_id}
    return SimpleNamespace(
        decision=SimpleNamespace(decision_id=decision_id, payload=payload),
        metadata={} if metadata is None else metadata,
    )


def test_recovery_helpers_normalize_plans_ids_and_tenants(monkeypatch: pytest.MonkeyPatch) -> None:
    assert recovery._recovery_plan(executor=SimpleNamespace(), env=object()) is None
    assert recovery._recovery_plan(executor=_Executor(plan_failure=True), env=object()) is None
    assert recovery._plan_action(None) == ""
    assert recovery._plan_action(SimpleNamespace(recovery_action=" Retry ")) == "retry"
    assert recovery._resolve_recovery_action(executor=_Executor(action="WAIT"), env=object()) == "wait"

    assert recovery._normalize_item({"x": 1}) == {"x": 1}
    assert recovery._normalize_item(None) == {}
    normalized = recovery._normalize_item(_Item())
    assert normalized["state"] == "pending"
    assert normalized["delivery_attempts"] == 2
    assert recovery._item_tenant_id({"tenant_id": " "}) == "default"
    assert recovery._decision_id_from_item({"decision_id": "  "}) == ""
    assert recovery._decision_id_from_item({"id": " id-1 "}) == "id-1"
    assert recovery._decision_id_from_item({"message_id": "m"}) == "m"

    monkeypatch.setattr(recovery, "_decision_tenant_id", lambda decision: "tenant-env")
    assert recovery._env_tenant_id(env=_env(), item={"tenant_id": "tenant-item"}) == "tenant-env"
    monkeypatch.setattr(recovery, "_decision_tenant_id", lambda decision: (_ for _ in ()).throw(RuntimeError("bad")))
    assert recovery._env_tenant_id(env=_env(), item={"tenant_id": "tenant-item"}) == "tenant-item"
    no_decision = SimpleNamespace(decision=None, metadata={"tenant_id": "tenant-meta"})
    assert recovery._resolve_recovery_tenant_id(env=no_decision, item={}) == "tenant-meta"
    assert recovery._resolve_recovery_tenant_id(env=SimpleNamespace(decision=None, metadata=[]), item={}) is None


def test_iter_recoverable_items_supports_all_legacy_surfaces_and_zero_limit() -> None:
    assert recovery._iter_recoverable_items(outbox=None, limit=1) == ()
    assert recovery._iter_recoverable_items(outbox=object(), limit=1) == ()

    all_box = SimpleNamespace(list_claimable_all=lambda *, limit: [_Item(), None])
    assert len(tuple(recovery._iter_recoverable_items(outbox=all_box, limit=2))) == 2
    assert recovery._iter_recoverable_items(outbox=all_box, limit=0) == ()
    bad_all = SimpleNamespace(list_claimable_all=lambda **kwargs: (_ for _ in ()).throw(RuntimeError("bad")))
    assert recovery._iter_recoverable_items(outbox=bad_all, limit=1) == ()

    direct = SimpleNamespace(list_claimable=lambda *, limit: [{"decision_id": "d"}])
    assert tuple(recovery._iter_recoverable_items(outbox=direct, limit=1))[0]["decision_id"] == "d"

    class _TenantBox:
        def list_claimable(self, *args, **kwargs):
            if "tenant_id" not in kwargs:
                raise TypeError("tenant required")
            return [_Item()]

    assert tuple(recovery._iter_recoverable_items(outbox=_TenantBox(), limit=1))[0]["tenant_id"] == "tenant-a"

    class _BrokenTenantBox:
        def list_claimable(self, *args, **kwargs):
            if "tenant_id" not in kwargs:
                raise TypeError("tenant required")
            raise RuntimeError("bad")

    assert recovery._iter_recoverable_items(outbox=_BrokenTenantBox(), limit=1) == ()
    generic_bad = SimpleNamespace(list_claimable=lambda **kwargs: (_ for _ in ()).throw(RuntimeError("bad")))
    assert recovery._iter_recoverable_items(outbox=generic_bad, limit=1) == ()

    pending = SimpleNamespace(list_pending=lambda *, limit: [_Item()])
    assert tuple(recovery._iter_recoverable_items(outbox=pending, limit=1))[0]["decision_id"] == "decision-1"
    pending_bad = SimpleNamespace(list_pending=lambda **kwargs: (_ for _ in ()).throw(RuntimeError("bad")))
    assert recovery._iter_recoverable_items(outbox=pending_bad, limit=1) == ()


def test_claim_terminal_and_quarantine_helpers_are_fail_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple] = []
    monkeypatch.setattr(recovery, "claim_or_skip", lambda *args, **kwargs: calls.append(("claim", kwargs)) or True)
    monkeypatch.setattr(recovery, "get_delivery_info", lambda *args, **kwargs: {"status": "delivering"})
    assert recovery._ensure_claim_or_skip(outbox=object(), item={"decision_id": "d", "tenant_id": "t", "status": "delivering"}) is True
    assert calls == []
    assert recovery._ensure_claim_or_skip(outbox=object(), item={}) is False

    monkeypatch.setattr(recovery, "get_delivery_info", lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("bad")))
    assert recovery._ensure_claim_or_skip(outbox=object(), item={"decision_id": "d", "tenant_id": "t", "state": "delivering"}) is True
    monkeypatch.setattr(recovery, "claim_or_skip", lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("bad")))
    assert recovery._ensure_claim_or_skip(outbox=object(), item={"decision_id": "d"}) is False

    quarantine: list[tuple[object, str]] = []
    terminal: list[tuple[object, str]] = []
    monkeypatch.setattr(recovery, "quarantine_recovery_outcome", lambda *, executor, env, reason: quarantine.append((env, reason)))
    monkeypatch.setattr(recovery, "finalize_terminal_recovery_outcome", lambda *, executor, env, reason, backend_name: terminal.append((env, reason)))
    recovery._quarantine_item(outbox=object(), env=SimpleNamespace(decision=None), item={}, reason="none")
    recovery._finalize_terminal_skip(outbox=object(), env=SimpleNamespace(decision=None), item={}, reason="none")
    assert not quarantine and not terminal
    recovery._quarantine_item(outbox=object(), env=SimpleNamespace(decision=None), item={"decision_id": "d", "tenant_id": "t"}, reason="q")
    recovery._finalize_terminal_skip(outbox=object(), env=SimpleNamespace(decision=None), item={"decision_id": "d", "tenant_id": "t"}, reason="s")
    assert quarantine[0][0].decision.payload["tenant_id"] == "t"
    assert terminal[0][0].decision.decision_id == "d"
    existing = _env()
    recovery._quarantine_item(outbox=object(), env=existing, item={"decision_id": "d"}, reason="existing")
    recovery._finalize_terminal_skip(outbox=object(), env=existing, item={"decision_id": "d"}, reason="existing")

    warnings: list[dict] = []
    monkeypatch.setattr(recovery, "_warn_recovery_issue", lambda **kwargs: warnings.append(kwargs))
    monkeypatch.setattr(recovery, "quarantine_recovery_outcome", lambda **kwargs: (_ for _ in ()).throw(RuntimeError("q")))
    monkeypatch.setattr(recovery, "finalize_terminal_recovery_outcome", lambda **kwargs: (_ for _ in ()).throw(RuntimeError("s")))
    recovery._quarantine_item(outbox=object(), env=existing, item={"decision_id": "d"}, reason="q")
    recovery._finalize_terminal_skip(outbox=object(), env=existing, item={"decision_id": "d"}, reason="s")
    assert {item["key"] for item in warnings} == {"recovery.dead_letter.move", "recovery.terminal_skip.finalize"}


def test_non_resume_actions_and_failure_classification(monkeypatch: pytest.MonkeyPatch) -> None:
    quarantines: list[str] = []
    terminals: list[str] = []
    logs: list[dict] = []
    monkeypatch.setattr(recovery, "_quarantine_item", lambda **kwargs: quarantines.append(kwargs["reason"]))
    monkeypatch.setattr(recovery, "_finalize_terminal_skip", lambda **kwargs: terminals.append(kwargs["reason"]))
    monkeypatch.setattr(recovery, "log_exception_throttled", lambda *args, **kwargs: logs.append(kwargs))
    item = {"decision_id": "d", "tenant_id": "tenant-a"}
    env = _env()
    assert recovery._handle_non_resume_action(action="dead_letter", outbox=object(), env=env, item=item)
    assert recovery._handle_non_resume_action(action="skip", outbox=object(), env=env, item=item)
    assert recovery._handle_non_resume_action(action="wait", outbox=object(), env=env, item=item)
    assert recovery._handle_non_resume_action(action="mystery", outbox=object(), env=env, item=item)
    assert not recovery._handle_non_resume_action(action="retry", outbox=object(), env=env, item=item)
    assert not recovery._handle_non_resume_action(action="", outbox=object(), env=env, item=item)
    assert quarantines == ["recovery_plan_dead_letter", "unknown_recovery_action_mystery"]
    assert terminals == ["recovery_plan_skip"]

    recovery._handle_recovery_execution_failure(outbox=object(), env=SimpleNamespace(decision=None, metadata={}), item={"decision_id": "d"}, exc=RuntimeError("x"))
    assert quarantines[-1].startswith("missing_recovery_tenant")
    class DecisionExpired(Exception):
        pass
    recovery._handle_recovery_execution_failure(outbox=object(), env=env, item=item, exc=DecisionExpired("expired"))
    assert quarantines[-1] == "DecisionExpired"
    recovery._handle_recovery_execution_failure(outbox=object(), env=env, item=item, exc=RuntimeError("DECISION_EXPIRED remote"))
    assert quarantines[-1] == "RuntimeError"
    recovery._handle_recovery_execution_failure(outbox=object(), env=env, item=item, exc=KeyError("other"))
    assert quarantines[-1] == "KeyError"
    assert logs


def test_recover_pending_covers_missing_archive_actions_claim_and_execution(monkeypatch: pytest.MonkeyPatch) -> None:
    assert recovery.recover_pending(executor=_Executor(), outbox=None, archive=_Archive({})) == 0
    assert recovery.recover_pending(executor=_Executor(), outbox=object(), archive=None) == 0

    items = [
        {},
        {"decision_id": "missing", "tenant_id": "tenant-a"},
        {"decision_id": "dead", "tenant_id": "tenant-a"},
        {"decision_id": "skip", "tenant_id": "tenant-a"},
        {"decision_id": "wait", "tenant_id": "tenant-a"},
        {"decision_id": "unclaimed", "tenant_id": "tenant-a"},
        {"decision_id": "ok", "tenant_id": "tenant-a"},
        {"decision_id": "fail", "tenant_id": "tenant-a"},
    ]
    outbox = SimpleNamespace(list_claimable_all=lambda *, limit: items[:limit])
    envs = {key: _env(decision_id=key) for key in ("dead", "skip", "wait", "unclaimed", "ok", "fail")}
    archive = _Archive(envs)
    actions = {"dead": "quarantine", "skip": "noop", "wait": "wait", "unclaimed": "resume", "ok": "resume", "fail": "resume"}
    executor = _Executor()
    executor._reliability = SimpleNamespace(plan=lambda env: SimpleNamespace(recovery_action=actions[env.decision.decision_id]))

    quarantines: list[str] = []
    terminals: list[str] = []
    failures: list[str] = []
    monkeypatch.setattr(recovery, "_quarantine_item", lambda **kwargs: quarantines.append(kwargs["reason"]))
    monkeypatch.setattr(recovery, "_finalize_terminal_skip", lambda **kwargs: terminals.append(kwargs["reason"]))
    monkeypatch.setattr(recovery, "_ensure_claim_or_skip", lambda *, outbox, item: item.get("decision_id") != "unclaimed")
    original_execute = executor.execute_recovery
    def _execute(env):
        if env.decision.decision_id == "fail":
            raise RuntimeError("boom")
        original_execute(env)
    executor.execute_recovery = _execute
    monkeypatch.setattr(recovery, "_handle_recovery_execution_failure", lambda **kwargs: failures.append(kwargs["item"]["decision_id"]))

    assert recovery.recover_pending(executor=executor, outbox=outbox, archive=archive, limit=20) == 1
    assert [env.decision.decision_id for env in executor.executed] == ["ok"]
    assert "missing_archive_envelope" in quarantines
    assert "recovery_plan_quarantine" in quarantines
    assert terminals == ["recovery_plan_noop"]
    assert failures == ["fail"]
    assert recovery.recover_pending(executor=executor, outbox=outbox, archive=archive, limit=0) == 0


def test_recovery_remaining_warning_and_tenant_fallback_branches(monkeypatch: pytest.MonkeyPatch) -> None:
    warnings: list[dict] = []
    monkeypatch.setattr(recovery, "log_exception_throttled", lambda *args, **kwargs: warnings.append(kwargs))
    recovery._warn_recovery_issue(key="k", msg="m", exc=ValueError("x"))
    assert warnings[0]["throttle_ms"] == 60_000

    monkeypatch.setattr(recovery, "_decision_tenant_id", lambda decision: " ")
    env = _env(tenant_id=None)
    assert recovery._env_tenant_id(env=env, item={"tenant_id": "tenant-item"}) == "tenant-item"
