from __future__ import annotations

import json
import time
from datetime import UTC, datetime
from multiprocessing import get_context
from pathlib import Path
from threading import Thread
from types import SimpleNamespace

import pytest

from application.business_autonomy.contracts import (
    BusinessExecutionRequest,
    BusinessExecutionResult,
    BusinessGoalEnvelope,
    ExecutionVerdict,
    IntegrationMode,
)
from application.business_autonomy.delayed_outcome_bridge import (
    BusinessAutonomyDelayedOutcomeBridge,
    DelayedOutcomeActionRecord,
)


def bridge(tmp_path: Path) -> BusinessAutonomyDelayedOutcomeBridge:
    return BusinessAutonomyDelayedOutcomeBridge(
        path=tmp_path / "delayed_outcomes.jsonl",
        state_path=tmp_path / "delayed_outcome_state.json",
        quarantine_path=tmp_path / "delayed_outcome_quarantine.jsonl",
        sweep_journal_path=tmp_path / "delayed_outcome_sweep_runs.jsonl",
        action_journal_path=tmp_path / "delayed_outcome_actions.jsonl",
        action_ledger_path=tmp_path / "delayed_outcome_action_ledger.jsonl",
    )


def request(*, execution_id: str = "e1", horizon: str = "week"):
    req = BusinessExecutionRequest(
        envelope=BusinessGoalEnvelope(
            business_id="b1",
            goal_id="g1",
            goal_type="grow",
            metadata={"tenant_id": "tenant-a", "planning_horizon": horizon},
        ),
        integration_mode=IntegrationMode.PLATFORM_DIRECT,
    )
    result = BusinessExecutionResult(
        verdict=ExecutionVerdict.ACCEPTED,
        business_id="b1",
        goal_id="g1",
        execution_id=execution_id,
        message="accepted",
        adapter_name="provider",
        metadata={"tenant_id": "tenant-a"},
    )
    return req, result


def _append_pending_in_process(root: str, execution_id: str, gate, results) -> None:
    item = bridge(Path(root))
    original_read = BusinessAutonomyDelayedOutcomeBridge._read_state

    def delayed_read(self):
        state = original_read(self)
        time.sleep(0.15)
        return state

    BusinessAutonomyDelayedOutcomeBridge._read_state = delayed_read
    gate.wait(10)
    req, result = request(execution_id=execution_id)
    reference = item.append_pending(request=req, result=result)
    results.put(reference.outcome_id if reference is not None else "")


def quarantined_row(outcome_id: str = "out-1") -> dict:
    return {
        "outcome_id": outcome_id,
        "execution_id": "exec-1",
        "tenant_id": "tenant-a",
        "business_id": "biz-a",
        "goal_id": "goal-a",
        "expected_ready_at_utc": "2026-01-01T00:00:00+00:00",
        "metadata": {"planning_horizon": "week"},
        "quarantine_reason": "delayed_outcome_stale",
        "quarantined_at_utc": "2026-01-02T00:00:00+00:00",
    }


def test_zero_limits_return_no_rows_and_malformed_json_objects_are_ignored(tmp_path: Path) -> None:
    item = bridge(tmp_path)
    (tmp_path / "delayed_outcome_sweep_runs.jsonl").write_text(
        "[]\nnot-json\n" + json.dumps({
            "run_id": "run-1", "operation": "sweep", "started_at_utc": "s",
            "completed_at_utc": "c", "active_before": 1, "active_after": 0,
            "quarantined_added": 1, "status": "completed", "linked_outcome_ids": ["out-1"],
            "metadata": {},
        }) + "\n",
        encoding="utf-8",
    )
    action_path = tmp_path / "delayed_outcome_actions.jsonl"
    action_path.write_text(
        "42\n{bad\n" + json.dumps({
            "action_id": "a1", "action_type": "release", "outcome_id": "out-1",
            "actor": "operator", "reason": "ok", "run_id": "run-1",
            "created_at_utc": "c", "metadata": {},
        }) + "\n",
        encoding="utf-8",
    )
    assert item.list_sweep_runs(limit=0) == ()
    assert item.list_action_runs(limit=0) == ()
    assert item.list_sweep_runs(limit=1)[0].run_id == "run-1"
    assert item.list_action_runs(limit=1)[0].action == "release"


def test_unknown_recovery_transition_is_not_reported_as_resumed(tmp_path: Path) -> None:
    item = bridge(tmp_path)
    item._write_state({
        "active": {}, "resolved": {}, "quarantined": {},
        "run_state": {
            "run_id": "mystery-1", "operation": "mystery", "status": "in_progress",
            "pending_transition": {"operation": "mystery", "outcome_id": "out-1"},
            "metadata": {}, "checkpoints": [],
        },
    })
    records = item.recover_incomplete_runs(recovered_by="test")
    assert records[0].metadata["resumed"] is False
    assert records[0].metadata["pending_transition"]["operation"] == "mystery"


def test_concurrent_bridge_instances_do_not_lose_pending_outcomes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    first = bridge(tmp_path)
    second = bridge(tmp_path)
    original_read = BusinessAutonomyDelayedOutcomeBridge._read_state

    def synchronized_read(self):
        state = original_read(self)
        time.sleep(0.1)
        return state

    monkeypatch.setattr(BusinessAutonomyDelayedOutcomeBridge, "_read_state", synchronized_read)
    errors: list[BaseException] = []

    def append(instance, execution_id):
        try:
            req, result = request(execution_id=execution_id)
            instance.append_pending(request=req, result=result)
        except BaseException as exc:
            errors.append(exc)

    threads = [Thread(target=append, args=(first, "e1")), Thread(target=append, args=(second, "e2"))]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=10)
    assert errors == []
    assert set(original_read(first)["active"]) == {"bo:e1", "bo:e2"}


def test_state_mutation_lock_rolls_back_after_body_failure(tmp_path: Path) -> None:
    import application.business_autonomy.delayed_outcome_bridge as module

    state_path = tmp_path / "state.json"
    with pytest.raises(RuntimeError, match="mutation failed"):
        with module._state_mutation_lock(state_path):
            raise RuntimeError("mutation failed")
    with module._state_mutation_lock(state_path):
        assert module._state_lock_path(state_path).exists()


def test_cross_process_bridge_instances_do_not_lose_pending_outcomes(tmp_path: Path) -> None:
    context = get_context("spawn")
    gate = context.Event()
    results = context.Queue()
    processes = [
        context.Process(
            target=_append_pending_in_process,
            args=(str(tmp_path), execution_id, gate, results),
        )
        for execution_id in ("process-1", "process-2")
    ]
    for process in processes:
        process.start()
    gate.set()
    for process in processes:
        process.join(timeout=20)
        assert process.exitcode == 0
    assert {results.get(timeout=5), results.get(timeout=5)} == {
        "bo:process-1",
        "bo:process-2",
    }
    assert set(bridge(tmp_path)._read_state()["active"]) == {
        "bo:process-1",
        "bo:process-2",
    }


def test_paths_default_properties_and_append_contracts(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import application.business_autonomy.delayed_outcome_bridge as module

    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    default = BusinessAutonomyDelayedOutcomeBridge.default()
    assert default.path == tmp_path / "business_autonomy" / "delayed_outcomes.jsonl"
    assert module.business_autonomy_delayed_outcome_state_path().name == "delayed_outcome_state.json"
    assert module.business_autonomy_delayed_outcome_quarantine_path().name.endswith("quarantine.jsonl")
    assert module.business_autonomy_delayed_outcome_sweep_journal_path().name.endswith("sweep_runs.jsonl")
    assert module.business_autonomy_delayed_outcome_action_journal_path().name.endswith("actions.jsonl")
    assert module.business_autonomy_delayed_outcome_action_ledger_path().name.endswith("ledger.jsonl")
    assert module._safe_mapping([]) == {}

    req, result = request(execution_id="rejected")
    rejected = SimpleNamespace(**{**result.__dict__, "verdict": "rejected"})
    assert default.append_pending(request=req, result=rejected) is None

    pending = SimpleNamespace(**{**result.__dict__, "execution_id": "pending", "verdict": "pending"})
    ref = default.append_pending(request=req, result=pending)
    assert ref is not None and ref.outcome_id == "bo:pending"
    assert default.list_active(tenant_id="tenant-a")[0].metadata["verdict"] == "pending"
    assert default.list_active(tenant_id="other") == ()

    record = DelayedOutcomeActionRecord("a", "retry", "o", "actor", "reason", "r", "now", {})
    assert record.action_type == "retry"
    assert record.reason == "reason"


def test_mark_resolved_active_quarantine_and_missing(tmp_path: Path) -> None:
    item = bridge(tmp_path)
    req, result = request(execution_id="active")
    ref = item.append_pending(request=req, result=result)
    assert ref is not None
    item.mark_resolved(outcome_id=ref.outcome_id, resolution="done", metadata={"score": 1})
    state = item._read_state()
    assert state["active"] == {}
    assert state["resolved"][ref.outcome_id]["resolution"] == "done"

    state["quarantined"] = {"q1": quarantined_row("q1")}
    item._write_state(state)
    item.mark_resolved(outcome_id="q1", resolution="manual")
    state = item._read_state()
    assert "q1" not in state["quarantined"]
    assert state["resolved"]["q1"]["status"] == "resolved"
    before = state
    item.mark_resolved(outcome_id="missing", resolution="ignored")
    assert item._read_state() == before


def test_sweep_covers_missing_invalid_naive_stale_and_active_rows(tmp_path: Path) -> None:
    item = bridge(tmp_path)
    now = datetime(2026, 1, 10, tzinfo=UTC)
    item._write_state({
        "active": {
            "missing": {**quarantined_row("missing"), "expected_ready_at_utc": ""},
            "invalid": {**quarantined_row("invalid"), "expected_ready_at_utc": "not-a-date"},
            "naive": {**quarantined_row("naive"), "expected_ready_at_utc": "2026-01-09T00:00:00"},
            "future": {**quarantined_row("future"), "expected_ready_at_utc": "2026-01-11T00:00:00+00:00"},
        },
        "resolved": {}, "quarantined": {}, "run_state": {},
    })
    result = item.sweep_expired(now=now)
    assert result.active_count == 1
    assert result.quarantined_count == 3
    state = item._read_state()
    assert set(state["quarantined"]) == {"missing", "invalid", "naive"}
    assert state["quarantined"]["missing"]["quarantine_reason"] == "missing_expected_ready_at_utc"
    assert state["quarantined"]["invalid"]["quarantine_reason"] == "invalid_expected_ready_at_utc"
    assert state["quarantined"]["naive"]["quarantine_reason"] == "delayed_outcome_stale"
    assert item.quarantine_summary()["quarantined_total"] == 3
    assert item.list_quarantined(tenant_id="other") == ()


def test_release_retry_journals_dedup_and_missing_paths(tmp_path: Path) -> None:
    item = bridge(tmp_path)
    assert item.release_quarantined(outcome_id="missing", released_by="op") is False
    assert item.retry_quarantined(outcome_id="missing", retried_by="op") is False
    assert item.list_sweep_runs() == ()
    assert item.list_action_runs() == ()
    assert item.list_action_ledger() == ()

    item._write_state({"active": {}, "resolved": {}, "quarantined": {"q1": quarantined_row("q1")}, "run_state": {}})
    assert item.release_quarantined(outcome_id="q1", released_by=" op ", note=" ok ") is True
    actions = item.list_action_runs(limit=10)
    assert actions[0].actor == "op" and actions[0].note == "ok"
    assert item.list_action_ledger(limit=10)[0].run_id == actions[0].run_id
    assert item.list_sweep_runs(limit=10)[0].status == "released"

    state = item._read_state()
    state["quarantined"] = {"q1": {**state["active"].pop("q1"), "quarantine_reason": "stale", "quarantined_at_utc": "now"}}
    item._write_state(state)
    assert item.retry_quarantined(outcome_id="q1", retried_by="op", planning_horizon="custom", note="again") is True
    assert item.list_action_runs(limit=1)[0].action == "retry"
    assert item._read_state()["active"]["q1"]["retry_metadata"]["planning_horizon"] == "custom"

    duplicate = item.list_action_runs(limit=1)[0]
    before = (tmp_path / "delayed_outcome_actions.jsonl").read_text(encoding="utf-8")
    item._append_action(duplicate)
    assert (tmp_path / "delayed_outcome_actions.jsonl").read_text(encoding="utf-8") == before


def test_recovery_without_run_and_with_checkpoints(tmp_path: Path) -> None:
    item = bridge(tmp_path)
    assert item.recover_incomplete_runs(recovered_by="none") == ()
    item._write_state({
        "active": {}, "resolved": {}, "quarantined": {},
        "run_state": {
            "run_id": "run-1", "operation": "sweep", "status": "in_progress",
            "started_at_utc": "start", "active_before": 2, "quarantined_before": 0,
            "linked_outcome_ids": ["a"], "checkpoints": [{"name": "one"}],
            "pending_transition": {}, "metadata": {"phase": "x"},
        },
    })
    record = item.recover_incomplete_runs(recovered_by="worker")[0]
    assert record.metadata["checkpoints"] == [{"name": "one"}]
    assert record.metadata["resumed"] is False
    assert item._read_state()["run_state"] == {}


def test_resume_sweep_release_retry_and_invalid_transitions(tmp_path: Path) -> None:
    item = bridge(tmp_path)
    base = quarantined_row("out-1")
    base.pop("quarantine_reason")
    base.pop("quarantined_at_utc")

    sweep_state = {
        "active": {"out-1": base}, "resolved": {}, "quarantined": {},
        "run_state": {
            "run_id": "sweep-1", "operation": "sweep", "status": "in_progress",
            "pending_transition": {"operation": "sweep", "outcome_id": "out-1", "row": base, "reason": "stale", "run_id": "sweep-1"},
            "linked_outcome_ids": [], "checkpoints": [], "metadata": {},
        },
    }
    item._write_state(sweep_state)
    rec = item.recover_incomplete_runs(recovered_by="test")[0]
    assert rec.metadata["resumed"] is True
    assert "out-1" in item._read_state()["quarantined"]

    release_row = {**base, "status": "pending"}
    item._write_state({
        "active": {}, "resolved": {}, "quarantined": {"out-1": quarantined_row("out-1")},
        "run_state": {
            "run_id": "release-1", "operation": "release", "status": "in_progress",
            "pending_transition": {"operation": "release", "outcome_id": "out-1", "row": release_row, "actor": "op", "reason": "ok", "metadata": {}},
            "linked_outcome_ids": [], "checkpoints": [], "metadata": {},
        },
    })
    assert item.recover_incomplete_runs(recovered_by="test")[0].metadata["resumed"] is True
    assert item.list_action_runs(limit=1)[0].action == "release"

    item._write_state({
        "active": {"out-1": release_row}, "resolved": {}, "quarantined": {},
        "run_state": {
            "run_id": "retry-1", "operation": "retry", "status": "in_progress",
            "pending_transition": {"operation": "retry", "outcome_id": "out-1", "row": release_row, "actor": "op", "note": "retry", "metadata": {"planning_horizon": "day"}},
            "linked_outcome_ids": ["out-1"], "checkpoints": [], "metadata": {},
        },
    })
    assert item.recover_incomplete_runs(recovered_by="test")[0].metadata["resumed"] is True
    assert item.list_action_runs(limit=1)[0].action == "retry"

    for operation, transition in [
        ("sweep", {"operation": "sweep", "outcome_id": "", "row": {}}),
        ("release", {"operation": "release", "outcome_id": "out-1", "row": {}}),
    ]:
        item._write_state({
            "active": {}, "resolved": {}, "quarantined": {},
            "run_state": {"run_id": f"{operation}-bad", "operation": operation, "status": "in_progress", "pending_transition": transition, "metadata": {}},
        })
        rec = item.recover_incomplete_runs(recovered_by="test")[0]
        assert rec.metadata["resumed"] is False
        assert rec.metadata["pending_transition"] == transition


def test_private_checkpoint_completion_and_corrupt_state_paths(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    item = bridge(tmp_path)
    assert item._read_state() == {"active": {}, "resolved": {}, "quarantined": {}, "run_state": {}}
    item.state_path.write_text("not-json", encoding="utf-8")
    assert item._read_state()["active"] == {}
    item.state_path.write_text("[]", encoding="utf-8")
    assert item._read_state()["active"] == {}
    item.state_path.write_text('{"active": [], "resolved": null, "quarantined": 1, "run_state": "x"}', encoding="utf-8")
    assert item._read_state() == {"active": {}, "resolved": {}, "quarantined": {}, "run_state": {}}

    run_id = item._begin_run(operation="sweep", metadata={"x": 1})
    item._checkpoint_run("wrong", "ignored")
    assert item._read_state()["run_state"]["checkpoints"] == []
    item._checkpoint_run(run_id, "ok")
    assert item._read_state()["run_state"]["checkpoints"][0]["name"] == "ok"
    item._complete_run(run_id="other", operation="sweep", active_before=0, active_after=0, quarantined_added=0, linked_outcome_ids=(), status="completed", metadata={})
    assert item._read_state()["run_state"]["run_id"] == run_id

    original_replace = Path.replace

    def fail_replace(self, target):
        raise OSError("replace failed")

    monkeypatch.setattr(Path, "replace", fail_replace)
    with pytest.raises(OSError, match="replace failed"):
        item._write_state({"active": {}, "resolved": {}, "quarantined": {}, "run_state": {}})
    monkeypatch.setattr(Path, "replace", original_replace)
    assert list(tmp_path.glob("*.tmp")) == []


def test_existing_action_parser_and_quarantine_dedup(tmp_path: Path) -> None:
    item = bridge(tmp_path)
    assert item._has_existing_action(path=tmp_path / "missing", outcome_id="o", run_id="r", action="a") is False
    path = tmp_path / "mixed.jsonl"
    path.write_text("\nnot-json\n[]\n" + json.dumps({"outcome_id": "other", "run_id": "r", "action": "a"}) + "\n" + json.dumps({"outcome_id": "o", "quarantine_run_id": "r", "action_type": "quarantine"}) + "\n", encoding="utf-8")
    assert item._has_existing_action(path=path, outcome_id="o", run_id="r", action="quarantine") is True
    assert item._has_existing_action(path=path, outcome_id="o", run_id="r", action="other") is False

    row = {**quarantined_row("o"), "quarantine_run_id": "r"}
    item.quarantine_path.write_text(json.dumps({**row, "action_type": "quarantine"}) + "\n", encoding="utf-8")
    before = item.quarantine_path.read_text(encoding="utf-8")
    item._append_quarantine(reason="stale", row=row)
    assert item.quarantine_path.read_text(encoding="utf-8") == before


def test_remaining_helper_and_recovery_idempotency_branches(tmp_path: Path) -> None:
    import application.business_autonomy.delayed_outcome_bridge as module

    item = bridge(tmp_path)
    assert list(module._json_object_lines(tmp_path / "absent.jsonl")) == []
    assert item._resume_pending_transition(
        state={"active": {}, "resolved": {}, "quarantined": {}, "run_state": {}},
        run_state={},
    ) is False

    run_id = item._begin_run(operation="manual", metadata={})
    item._complete_run(
        run_id=run_id,
        operation="manual",
        active_before=0,
        active_after=0,
        quarantined_added=0,
        linked_outcome_ids=(),
        status="completed",
        metadata={},
    )
    assert item._read_state()["run_state"] == {}

    row = quarantined_row("out-1")
    row.pop("quarantine_reason")
    row.pop("quarantined_at_utc")
    state = {
        "active": {},
        "resolved": {},
        "quarantined": {"out-1": {**row, "status": "quarantined"}},
        "run_state": {
            "run_id": "different",
            "operation": "sweep",
            "status": "in_progress",
            "pending_transition": {},
            "linked_outcome_ids": [],
            "checkpoints": [],
        },
    }
    item._write_state(state)
    assert item._resume_pending_transition(
        state=state,
        run_state={
            "run_id": "sweep-original",
            "operation": "sweep",
            "pending_transition": {
                "operation": "sweep",
                "outcome_id": "out-1",
                "row": row,
                "reason": "stale",
            },
        },
    ) is True
    assert item._read_state()["run_state"]["run_id"] == "different"
