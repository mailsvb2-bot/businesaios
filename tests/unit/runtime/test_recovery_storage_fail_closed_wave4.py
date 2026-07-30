from __future__ import annotations

from types import SimpleNamespace

import pytest

import runtime.recovery as subject


def _env(decision_id: str = "d-1"):
    return SimpleNamespace(decision=SimpleNamespace(decision_id=decision_id, payload={"tenant_id": "tenant-1"}))


class _Archive:
    def get(self, decision_id: str):
        return _env(decision_id)


def test_plan_storage_outage_blocks_claim_and_dispatch(monkeypatch) -> None:
    calls: list[str] = []
    executor = SimpleNamespace(
        _reliability=SimpleNamespace(plan=lambda _env: (_ for _ in ()).throw(OSError("PLAN_STORE_DOWN"))),
        execute_recovery=lambda _env: calls.append("dispatch"),
    )
    outbox = SimpleNamespace(list_claimable_all=lambda *, limit: [{"decision_id": "d-1", "tenant_id": "tenant-1"}])
    monkeypatch.setattr(subject, "claim_or_skip", lambda *args, **kwargs: calls.append("claim") or True)

    with pytest.raises(OSError, match="PLAN_STORE_DOWN"):
        subject.recover_pending(executor=executor, outbox=outbox, archive=_Archive())

    assert calls == []


@pytest.mark.parametrize("method", ["list_claimable_all", "list_pending"])
def test_type_error_without_signature_fallback_is_an_enumeration_outage(monkeypatch, method: str) -> None:
    warnings: list[str] = []
    outbox = SimpleNamespace(
        **{method: lambda **kwargs: (_ for _ in ()).throw(TypeError("OUTBOX_READ_FAILED"))}
    )
    monkeypatch.setattr(subject, "_warn_recovery_issue", lambda **kwargs: warnings.append(kwargs["key"]))

    assert subject._iter_recoverable_items(outbox=outbox, limit=1) == ()
    assert warnings == [f"recovery.outbox.{method}"]


def test_delivering_ownership_read_outage_never_attempts_reclaim(monkeypatch) -> None:
    calls: list[str] = []
    warnings: list[str] = []
    monkeypatch.setattr(subject, "get_delivery_info", lambda *args, **kwargs: (_ for _ in ()).throw(OSError("OWNER_STORE_DOWN")))
    monkeypatch.setattr(subject, "claim_or_skip", lambda *args, **kwargs: calls.append("claim") or True)
    monkeypatch.setattr(subject, "_warn_recovery_issue", lambda **kwargs: warnings.append(kwargs["key"]))

    claimed = subject._ensure_claim_or_skip(
        outbox=object(),
        item={"decision_id": "d-1", "tenant_id": "tenant-1", "status": "delivering"},
    )

    assert claimed is False
    assert calls == []
    assert warnings == ["recovery.claim.ownership_read"]


def test_terminal_finalization_outage_does_not_resume_effect(monkeypatch) -> None:
    calls: list[str] = []
    executor = SimpleNamespace(
        _reliability=SimpleNamespace(plan=lambda _env: SimpleNamespace(recovery_action="noop")),
        execute_recovery=lambda _env: calls.append("dispatch"),
    )
    outbox = SimpleNamespace(list_claimable_all=lambda *, limit: [{"decision_id": "d-1", "tenant_id": "tenant-1"}])
    monkeypatch.setattr(subject, "finalize_terminal_recovery_outcome", lambda **kwargs: (_ for _ in ()).throw(OSError("FINALIZE_DOWN")))

    with pytest.raises(OSError, match="FINALIZE_DOWN"):
        subject.recover_pending(executor=executor, outbox=outbox, archive=_Archive())

    assert calls == []
