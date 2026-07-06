from __future__ import annotations

import json
import os
import tempfile
from collections.abc import Mapping
from contextlib import suppress
from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from uuid import uuid4

from application.business_autonomy.contracts import BusinessExecutionRequest, BusinessExecutionResult

_DELAY_BY_HORIZON = {
    "now": timedelta(minutes=15),
    "today": timedelta(hours=6),
    "day": timedelta(hours=6),
    "week": timedelta(days=7),
    "month": timedelta(days=30),
    "quarter": timedelta(days=90),
}


def business_autonomy_delayed_outcome_dir() -> Path:
    root = Path(os.getenv("DATA_DIR", "runtime/data")) / "business_autonomy"
    root.mkdir(parents=True, exist_ok=True)
    return root


def business_autonomy_delayed_outcome_path() -> Path:
    return business_autonomy_delayed_outcome_dir() / "delayed_outcomes.jsonl"


def business_autonomy_delayed_outcome_state_path() -> Path:
    return business_autonomy_delayed_outcome_dir() / "delayed_outcome_state.json"


def business_autonomy_delayed_outcome_quarantine_path() -> Path:
    return business_autonomy_delayed_outcome_dir() / "delayed_outcome_quarantine.jsonl"


def business_autonomy_delayed_outcome_sweep_journal_path() -> Path:
    return business_autonomy_delayed_outcome_dir() / "delayed_outcome_sweep_runs.jsonl"


def business_autonomy_delayed_outcome_action_journal_path() -> Path:
    return business_autonomy_delayed_outcome_dir() / "delayed_outcome_actions.jsonl"


def business_autonomy_delayed_outcome_action_ledger_path() -> Path:
    return business_autonomy_delayed_outcome_dir() / "delayed_outcome_action_ledger.jsonl"


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _safe_mapping(value: object) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _append_jsonl_line(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(dict(payload), ensure_ascii=False, sort_keys=True))
        fh.write("\n")


@dataclass(frozen=True)
class BusinessDelayedOutcomeReference:
    outcome_id: str
    execution_id: str
    tenant_id: str
    business_id: str
    goal_id: str
    expected_ready_at_utc: str
    metadata: dict[str, Any]


@dataclass(frozen=True)
class DelayedOutcomeSweepResult:
    active_count: int
    quarantined_count: int


@dataclass(frozen=True)
class DelayedOutcomeSweepRunRecord:
    run_id: str
    operation: str
    started_at_utc: str
    completed_at_utc: str
    active_before: int
    active_after: int
    quarantined_added: int
    status: str
    linked_outcome_ids: tuple[str, ...]
    metadata: dict[str, Any]


@dataclass(frozen=True)
class BusinessDelayedOutcomeQuarantineEntry:
    outcome_id: str
    execution_id: str
    tenant_id: str
    business_id: str
    goal_id: str
    expected_ready_at_utc: str
    quarantine_reason: str
    quarantined_at_utc: str
    metadata: dict[str, Any]


@dataclass(frozen=True)
class DelayedOutcomeActionRecord:
    action_id: str
    action: str
    outcome_id: str
    actor: str
    note: str
    run_id: str
    created_at_utc: str
    metadata: dict[str, Any]

    @property
    def action_type(self) -> str:
        return self.action

    @property
    def reason(self) -> str:
        return self.note


@dataclass(frozen=True)
class BusinessAutonomyDelayedOutcomeBridge:
    path: Path
    state_path: Path
    quarantine_path: Path
    sweep_journal_path: Path | None = None
    action_journal_path: Path | None = None
    action_ledger_path: Path | None = None

    @classmethod
    def default(cls) -> BusinessAutonomyDelayedOutcomeBridge:
        return cls(
            path=business_autonomy_delayed_outcome_path(),
            state_path=business_autonomy_delayed_outcome_state_path(),
            quarantine_path=business_autonomy_delayed_outcome_quarantine_path(),
            sweep_journal_path=business_autonomy_delayed_outcome_sweep_journal_path(),
            action_journal_path=business_autonomy_delayed_outcome_action_journal_path(),
            action_ledger_path=business_autonomy_delayed_outcome_action_ledger_path(),
        )

    def append_pending(self, *, request: BusinessExecutionRequest, result: BusinessExecutionResult) -> BusinessDelayedOutcomeReference | None:
        verdict = str(result.verdict.value if hasattr(result.verdict, "value") else result.verdict).strip().lower()
        if verdict not in {"accepted", "pending"}:
            return None
        tenant_id = str(request.envelope.metadata.get("tenant_id") or result.metadata.get("tenant_id") or result.business_id).strip() or result.business_id
        planning_horizon = str(request.envelope.metadata.get("planning_horizon") or "week").strip().lower()
        expected_ready_at = _utc_now() + _DELAY_BY_HORIZON.get(planning_horizon, timedelta(days=7))
        reference = BusinessDelayedOutcomeReference(
            outcome_id=f"bo:{result.execution_id}",
            execution_id=result.execution_id,
            tenant_id=tenant_id,
            business_id=result.business_id,
            goal_id=result.goal_id,
            expected_ready_at_utc=expected_ready_at.isoformat(),
            metadata={"planning_horizon": planning_horizon, "adapter_name": result.adapter_name, "verdict": verdict},
        )
        _append_jsonl_line(self.path, asdict(reference))
        state = self._read_state()
        state["active"][reference.outcome_id] = {
            **asdict(reference),
            "status": "pending",
            "registered_at_utc": _utc_now().isoformat(),
        }
        self._write_state(state)
        return reference

    def mark_resolved(self, *, outcome_id: str, resolution: str, metadata: dict[str, Any] | None = None) -> None:
        state = self._read_state()
        active = _safe_mapping(state.get("active"))
        row = _safe_mapping(active.get(str(outcome_id)))
        if not row:
            row = _safe_mapping(_safe_mapping(state.get("quarantined")).get(str(outcome_id)))
            if not row:
                return
        row["status"] = "resolved"
        row["resolved_at_utc"] = _utc_now().isoformat()
        row["resolution"] = str(resolution or "").strip()
        row["resolution_metadata"] = dict(metadata or {})
        active.pop(str(outcome_id), None)
        resolved = _safe_mapping(state.get("resolved"))
        resolved[str(outcome_id)] = row
        quarantined = _safe_mapping(state.get("quarantined"))
        quarantined.pop(str(outcome_id), None)
        state["active"] = active
        state["resolved"] = resolved
        state["quarantined"] = quarantined
        self._write_state(state)

    def sweep_expired(self, *, now: datetime | None = None) -> DelayedOutcomeSweepResult:
        self.recover_incomplete_runs(recovered_by="sweeper")
        state = self._read_state()
        active = _safe_mapping(state.get("active"))
        active_before = len(active)
        current = (now or _utc_now()).astimezone(UTC)
        quarantined = _safe_mapping(state.get("quarantined"))
        quarantined_count = 0
        linked_outcome_ids: list[str] = []
        run_id = self._begin_run(operation="sweep", metadata={"recovered_before_start": True})
        for outcome_id, row in list(active.items()):
            normalized = _safe_mapping(row)
            expected = str(normalized.get("expected_ready_at_utc") or "").strip()
            if not expected:
                self._checkpoint_run(run_id, "sweep:missing_expected", pending_transition={"operation": "sweep", "outcome_id": str(outcome_id), "reason": "missing_expected_ready_at_utc", "row": normalized, "quarantined_at_utc": current.isoformat(), "run_id": run_id})
                self._move_to_quarantine(active=active, quarantined=quarantined, outcome_id=outcome_id, row=normalized, reason="missing_expected_ready_at_utc", current=current, run_id=run_id)
                self._checkpoint_run(run_id, "sweep:quarantined")
                quarantined_count += 1
                linked_outcome_ids.append(str(outcome_id))
                continue
            try:
                expected_dt = datetime.fromisoformat(expected)
            except ValueError:
                self._checkpoint_run(run_id, "sweep:invalid_expected", pending_transition={"operation": "sweep", "outcome_id": str(outcome_id), "reason": "invalid_expected_ready_at_utc", "row": normalized, "quarantined_at_utc": current.isoformat(), "run_id": run_id})
                self._move_to_quarantine(active=active, quarantined=quarantined, outcome_id=outcome_id, row=normalized, reason="invalid_expected_ready_at_utc", current=current, run_id=run_id)
                self._checkpoint_run(run_id, "sweep:quarantined")
                quarantined_count += 1
                linked_outcome_ids.append(str(outcome_id))
                continue
            if expected_dt.tzinfo is None:
                expected_dt = expected_dt.replace(tzinfo=UTC)
            if current > expected_dt:
                self._checkpoint_run(run_id, "sweep:stale", pending_transition={"operation": "sweep", "outcome_id": str(outcome_id), "reason": "delayed_outcome_stale", "row": normalized, "quarantined_at_utc": current.isoformat(), "run_id": run_id})
                self._move_to_quarantine(active=active, quarantined=quarantined, outcome_id=outcome_id, row=normalized, reason="delayed_outcome_stale", current=current, run_id=run_id)
                self._checkpoint_run(run_id, "sweep:quarantined")
                quarantined_count += 1
                linked_outcome_ids.append(str(outcome_id))
        state["active"] = active
        state["quarantined"] = quarantined
        self._write_state(state)
        self._complete_run(
            run_id=run_id,
            operation="sweep",
            active_before=active_before,
            active_after=len(active),
            quarantined_added=quarantined_count,
            linked_outcome_ids=tuple(linked_outcome_ids),
            status="completed",
            metadata={},
        )
        return DelayedOutcomeSweepResult(active_count=len(active), quarantined_count=quarantined_count)

    def recover_incomplete_runs(self, *, recovered_by: str) -> tuple[DelayedOutcomeSweepRunRecord, ...]:
        state = self._read_state()
        run_state = _safe_mapping(state.get("run_state"))
        if not run_state or str(run_state.get("status") or "") != "in_progress":
            return ()
        transition = _safe_mapping(run_state.get("pending_transition"))
        resumed = False
        if transition:
            resumed = self._resume_pending_transition(state=state, run_state=run_state)
            state = self._read_state()
            run_state = _safe_mapping(state.get("run_state"))
        metadata = {**_safe_mapping(run_state.get("metadata")), "recovered_by": str(recovered_by or "system"), "resumed": bool(resumed)}
        checkpoints = list(run_state.get("checkpoints") or [])
        if checkpoints:
            metadata["checkpoints"] = checkpoints
        record = DelayedOutcomeSweepRunRecord(
            run_id=str(run_state.get("run_id") or f"recover_{uuid4().hex}"),
            operation=str(run_state.get("operation") or "unknown"),
            started_at_utc=str(run_state.get("started_at_utc") or _utc_now().isoformat()),
            completed_at_utc=_utc_now().isoformat(),
            active_before=int(run_state.get("active_before") or 0),
            active_after=len(_safe_mapping(state.get("active"))),
            quarantined_added=max(0, len(_safe_mapping(state.get("quarantined"))) - int(run_state.get("quarantined_before") or 0)),
            status="interrupted",
            linked_outcome_ids=tuple(str(item) for item in list(run_state.get("linked_outcome_ids") or [])),
            metadata=metadata,
        )
        self._append_sweep_run(record)
        state["run_state"] = {}
        self._write_state(state)
        return (record,)

    def list_active(self, *, tenant_id: str | None = None) -> tuple[BusinessDelayedOutcomeReference, ...]:
        state = self._read_state()
        items: list[BusinessDelayedOutcomeReference] = []
        for row in _safe_mapping(state.get("active")).values():
            normalized = _safe_mapping(row)
            if tenant_id is not None and str(normalized.get("tenant_id") or "") != str(tenant_id):
                continue
            items.append(BusinessDelayedOutcomeReference(
                outcome_id=str(normalized.get("outcome_id") or ""),
                execution_id=str(normalized.get("execution_id") or ""),
                tenant_id=str(normalized.get("tenant_id") or ""),
                business_id=str(normalized.get("business_id") or ""),
                goal_id=str(normalized.get("goal_id") or ""),
                expected_ready_at_utc=str(normalized.get("expected_ready_at_utc") or ""),
                metadata=dict(normalized.get("metadata") or {}),
            ))
        return tuple(items)

    def list_quarantined(self, *, tenant_id: str | None = None) -> tuple[BusinessDelayedOutcomeQuarantineEntry, ...]:
        state = self._read_state()
        items: list[BusinessDelayedOutcomeQuarantineEntry] = []
        for row in _safe_mapping(state.get("quarantined")).values():
            normalized = _safe_mapping(row)
            if tenant_id is not None and str(normalized.get("tenant_id") or "") != str(tenant_id):
                continue
            items.append(BusinessDelayedOutcomeQuarantineEntry(
                outcome_id=str(normalized.get("outcome_id") or ""),
                execution_id=str(normalized.get("execution_id") or ""),
                tenant_id=str(normalized.get("tenant_id") or ""),
                business_id=str(normalized.get("business_id") or ""),
                goal_id=str(normalized.get("goal_id") or ""),
                expected_ready_at_utc=str(normalized.get("expected_ready_at_utc") or ""),
                quarantine_reason=str(normalized.get("quarantine_reason") or ""),
                quarantined_at_utc=str(normalized.get("quarantined_at_utc") or ""),
                metadata=dict(normalized.get("metadata") or {}),
            ))
        return tuple(items)

    def quarantine_summary(self) -> dict[str, Any]:
        rows = self.list_quarantined()
        by_reason: dict[str, int] = {}
        for item in rows:
            by_reason[item.quarantine_reason] = by_reason.get(item.quarantine_reason, 0) + 1
        return {"quarantined_total": len(rows), "by_reason": by_reason}

    def release_quarantined(self, *, outcome_id: str, released_by: str, note: str = "") -> bool:
        self.recover_incomplete_runs(recovered_by="release")
        state = self._read_state()
        quarantined = _safe_mapping(state.get("quarantined"))
        row = _safe_mapping(quarantined.get(str(outcome_id)))
        if not row:
            return False
        run_id = self._begin_run(operation="release", metadata={"outcome_id": str(outcome_id)})
        row.pop("quarantine_reason", None)
        row.pop("quarantined_at_utc", None)
        row["status"] = "pending"
        row["released_at_utc"] = _utc_now().isoformat()
        row["release_metadata"] = {"released_by": str(released_by or "").strip(), "note": str(note or "").strip(), "run_id": run_id}
        active = _safe_mapping(state.get("active"))
        self._checkpoint_run(run_id, "release:prepare", pending_transition={"operation": "release", "outcome_id": str(outcome_id), "row": row, "actor": str(released_by or "").strip(), "reason": str(note or "").strip(), "metadata": {}})
        active[str(outcome_id)] = row
        quarantined.pop(str(outcome_id), None)
        state["active"] = active
        state["quarantined"] = quarantined
        self._write_state(state)
        self._checkpoint_run(run_id, "release:state_written")
        self._append_action(
            DelayedOutcomeActionRecord(
                action_id=f"release_{uuid4().hex}",
                action="release",
                outcome_id=str(outcome_id),
                actor=str(released_by or "").strip(),
                note=str(note or "").strip(),
                run_id=run_id,
                created_at_utc=_utc_now().isoformat(),
                metadata={},
            )
        )
        self._checkpoint_run(run_id, "release:journal_written")
        self._complete_run(
            run_id=run_id,
            operation="release",
            active_before=max(0, len(active) - 1),
            active_after=len(active),
            quarantined_added=0,
            linked_outcome_ids=(str(outcome_id),),
            status="released",
            metadata={},
        )
        return True

    def retry_quarantined(self, *, outcome_id: str, retried_by: str, planning_horizon: str | None = None, note: str = "") -> bool:
        self.recover_incomplete_runs(recovered_by="retry")
        state = self._read_state()
        quarantined = _safe_mapping(state.get("quarantined"))
        row = _safe_mapping(quarantined.get(str(outcome_id)))
        if not row:
            return False
        run_id = self._begin_run(operation="retry", metadata={"outcome_id": str(outcome_id)})
        horizon = str(planning_horizon or _safe_mapping(row.get("metadata")).get("planning_horizon") or "week").strip().lower()
        expected_ready_at = _utc_now() + _DELAY_BY_HORIZON.get(horizon, timedelta(days=7))
        row.pop("quarantine_reason", None)
        row.pop("quarantined_at_utc", None)
        row["status"] = "pending"
        row["expected_ready_at_utc"] = expected_ready_at.isoformat()
        row["retry_metadata"] = {
            "retried_by": str(retried_by or "").strip(),
            "note": str(note or "").strip(),
            "planning_horizon": horizon,
            "run_id": run_id,
        }
        active = _safe_mapping(state.get("active"))
        self._checkpoint_run(run_id, "retry:prepare", pending_transition={"operation": "retry", "outcome_id": str(outcome_id), "row": row, "actor": str(retried_by or "").strip(), "reason": str(note or "").strip(), "metadata": {"planning_horizon": horizon}})
        active[str(outcome_id)] = row
        quarantined.pop(str(outcome_id), None)
        state["active"] = active
        state["quarantined"] = quarantined
        self._write_state(state)
        self._checkpoint_run(run_id, "retry:state_written")
        self._append_action(
            DelayedOutcomeActionRecord(
                action_id=f"retry_{uuid4().hex}",
                action="retry",
                outcome_id=str(outcome_id),
                actor=str(retried_by or "").strip(),
                note=str(note or "").strip(),
                run_id=run_id,
                created_at_utc=_utc_now().isoformat(),
                metadata={"planning_horizon": horizon},
            )
        )
        self._checkpoint_run(run_id, "retry:journal_written")
        self._complete_run(
            run_id=run_id,
            operation="retry",
            active_before=max(0, len(active) - 1),
            active_after=len(active),
            quarantined_added=0,
            linked_outcome_ids=(str(outcome_id),),
            status="retried",
            metadata={"planning_horizon": horizon},
        )
        return True

    def list_sweep_runs(self, *, limit: int = 100) -> tuple[DelayedOutcomeSweepRunRecord, ...]:
        path = self.sweep_journal_path or business_autonomy_delayed_outcome_sweep_journal_path()
        if not path.exists():
            return ()
        rows: list[DelayedOutcomeSweepRunRecord] = []
        for line in path.read_text(encoding="utf-8").splitlines():
            raw = line.strip()
            if not raw:
                continue
            try:
                payload = json.loads(raw)
            except json.JSONDecodeError:
                continue
            rows.append(
                DelayedOutcomeSweepRunRecord(
                    run_id=str(payload.get("run_id") or ""),
                    operation=str(payload.get("operation") or ""),
                    started_at_utc=str(payload.get("started_at_utc") or ""),
                    completed_at_utc=str(payload.get("completed_at_utc") or ""),
                    active_before=int(payload.get("active_before") or 0),
                    active_after=int(payload.get("active_after") or 0),
                    quarantined_added=int(payload.get("quarantined_added") or 0),
                    status=str(payload.get("status") or ""),
                    linked_outcome_ids=tuple(str(item) for item in list(payload.get("linked_outcome_ids") or [])),
                    metadata=dict(payload.get("metadata") or {}),
                )
            )
        return tuple(rows[-max(0, int(limit)) :][::-1])

    def list_action_runs(self, *, limit: int = 100) -> tuple[DelayedOutcomeActionRecord, ...]:
        path = self.action_journal_path or business_autonomy_delayed_outcome_action_journal_path()
        return self._read_action_records(path=path, limit=limit)

    def list_action_ledger(self, *, limit: int = 100) -> tuple[DelayedOutcomeActionRecord, ...]:
        path = self.action_ledger_path or business_autonomy_delayed_outcome_action_ledger_path()
        return self._read_action_records(path=path, limit=limit)

    def _read_action_records(self, *, path: Path, limit: int) -> tuple[DelayedOutcomeActionRecord, ...]:
        if not path.exists():
            return ()
        rows: list[DelayedOutcomeActionRecord] = []
        for line in path.read_text(encoding="utf-8").splitlines():
            raw = line.strip()
            if not raw:
                continue
            try:
                payload = json.loads(raw)
            except json.JSONDecodeError:
                continue
            rows.append(
                DelayedOutcomeActionRecord(
                    action_id=str(payload.get("action_id") or ""),
                    action=str(payload.get("action") or payload.get("action_type") or ""),
                    outcome_id=str(payload.get("outcome_id") or ""),
                    actor=str(payload.get("actor") or ""),
                    note=str(payload.get("note") or payload.get("reason") or ""),
                    run_id=str(payload.get("run_id") or ""),
                    created_at_utc=str(payload.get("created_at_utc") or ""),
                    metadata=dict(payload.get("metadata") or {}),
                )
            )
        return tuple(rows[-max(0, int(limit)) :][::-1])

    def _begin_run(self, *, operation: str, metadata: Mapping[str, Any]) -> str:
        state = self._read_state()
        run_id = f"{operation}_{uuid4().hex}"
        state["run_state"] = {
            "run_id": run_id,
            "operation": str(operation),
            "status": "in_progress",
            "started_at_utc": _utc_now().isoformat(),
            "active_before": len(_safe_mapping(state.get("active"))),
            "quarantined_before": len(_safe_mapping(state.get("quarantined"))),
            "linked_outcome_ids": [],
            "checkpoints": [],
            "pending_transition": {},
            "metadata": dict(metadata or {}),
        }
        self._write_state(state)
        return run_id

    def _complete_run(
        self,
        *,
        run_id: str,
        operation: str,
        active_before: int,
        active_after: int,
        quarantined_added: int,
        linked_outcome_ids: tuple[str, ...],
        status: str,
        metadata: Mapping[str, Any],
    ) -> None:
        state = self._read_state()
        current = _safe_mapping(state.get("run_state"))
        record = DelayedOutcomeSweepRunRecord(
            run_id=str(run_id),
            operation=str(operation),
            started_at_utc=str(current.get("started_at_utc") or _utc_now().isoformat()),
            completed_at_utc=_utc_now().isoformat(),
            active_before=int(active_before),
            active_after=int(active_after),
            quarantined_added=int(quarantined_added),
            status=str(status),
            linked_outcome_ids=tuple(str(item) for item in linked_outcome_ids),
            metadata=dict(metadata or {}),
        )
        self._append_sweep_run(record)
        if str(current.get("run_id") or "") == str(run_id):
            state["run_state"] = {}
            self._write_state(state)

    def _append_sweep_run(self, record: DelayedOutcomeSweepRunRecord) -> None:
        path = self.sweep_journal_path or business_autonomy_delayed_outcome_sweep_journal_path()
        _append_jsonl_line(path, {**asdict(record), "linked_outcome_ids": list(record.linked_outcome_ids)})

    def _append_action(self, record: DelayedOutcomeActionRecord) -> None:
        payload = {**asdict(record), "action_type": record.action, "reason": record.note}
        for path in filter(None, (self.action_journal_path or business_autonomy_delayed_outcome_action_journal_path(), self.action_ledger_path or business_autonomy_delayed_outcome_action_ledger_path())):
            if self._has_existing_action(path=path, outcome_id=record.outcome_id, run_id=record.run_id, action=record.action):
                continue
            _append_jsonl_line(path, payload)

    def _move_to_quarantine(
        self,
        *,
        active: dict[str, Any],
        quarantined: dict[str, Any],
        outcome_id: str,
        row: dict[str, Any],
        reason: str,
        current: datetime,
        run_id: str,
    ) -> None:
        normalized = dict(row)
        normalized["status"] = "quarantined"
        normalized["quarantined_at_utc"] = current.isoformat()
        normalized["quarantine_reason"] = str(reason)
        normalized["quarantine_run_id"] = str(run_id)
        quarantined[str(outcome_id)] = normalized
        active.pop(str(outcome_id), None)
        self._append_quarantine(reason=reason, row=normalized)

    def _append_quarantine(self, *, reason: str, row: Mapping[str, Any]) -> None:
        payload = dict(row)
        payload["quarantine_reason"] = str(reason)
        outcome_id = str(payload.get("outcome_id") or "")
        run_id = str(payload.get("quarantine_run_id") or "")
        if self._has_existing_action(path=self.quarantine_path, outcome_id=outcome_id, run_id=run_id, action="quarantine"):
            return
        _append_jsonl_line(self.quarantine_path, {**payload, "action_type": "quarantine"})


    def _has_existing_action(self, *, path: Path, outcome_id: str, run_id: str, action: str) -> bool:
        if not path.exists():
            return False
        for line in path.read_text(encoding="utf-8").splitlines():
            raw = line.strip()
            if not raw:
                continue
            try:
                payload = json.loads(raw)
            except json.JSONDecodeError:
                continue
            if str(payload.get("outcome_id") or "") == str(outcome_id) and str(payload.get("run_id") or payload.get("quarantine_run_id") or "") == str(run_id) and str(payload.get("action") or payload.get("action_type") or "") == str(action):
                return True
        return False

    def _checkpoint_run(self, run_id: str, checkpoint: str, *, pending_transition: Mapping[str, Any] | None = None) -> None:
        state = self._read_state()
        run_state = _safe_mapping(state.get("run_state"))
        if str(run_state.get("run_id") or "") != str(run_id):
            return
        checkpoints = list(run_state.get("checkpoints") or [])
        checkpoints.append({"name": str(checkpoint), "at_utc": _utc_now().isoformat()})
        run_state["checkpoints"] = checkpoints
        run_state["pending_transition"] = dict(pending_transition or {})
        state["run_state"] = run_state
        self._write_state(state)

    def _resume_pending_transition(self, *, state: dict[str, Any], run_state: Mapping[str, Any]) -> bool:
        transition = _safe_mapping(run_state.get("pending_transition"))
        if not transition:
            return False
        operation = str(run_state.get("operation") or transition.get("operation") or "")
        outcome_id = str(transition.get("outcome_id") or "")
        current = _utc_now()
        active = _safe_mapping(state.get("active"))
        quarantined = _safe_mapping(state.get("quarantined"))
        run_id = str(run_state.get("run_id") or transition.get("run_id") or "")
        if operation == "sweep":
            row = _safe_mapping(transition.get("row"))
            if row and outcome_id and outcome_id not in quarantined:
                normalized = dict(row)
                normalized["status"] = "quarantined"
                normalized["quarantined_at_utc"] = str(transition.get("quarantined_at_utc") or current.isoformat())
                normalized["quarantine_reason"] = str(transition.get("reason") or normalized.get("quarantine_reason") or "resume_quarantine")
                normalized["quarantine_run_id"] = run_id
                quarantined[outcome_id] = normalized
                active.pop(outcome_id, None)
                state["active"] = active
                state["quarantined"] = quarantined
                self._write_state(state)
                self._append_quarantine(reason=normalized["quarantine_reason"], row=normalized)
        elif operation in {"release", "retry"}:
            row = _safe_mapping(transition.get("row"))
            if row and outcome_id and outcome_id not in active:
                active[outcome_id] = dict(row)
                quarantined.pop(outcome_id, None)
                state["active"] = active
                state["quarantined"] = quarantined
                self._write_state(state)
            action = "release" if operation == "release" else "retry"
            actor = str(transition.get("actor") or "")
            note = str(transition.get("reason") or transition.get("note") or "")
            meta = dict(transition.get("metadata") or {})
            self._append_action(DelayedOutcomeActionRecord(
                action_id=f"{action}_{uuid4().hex}",
                action=action,
                outcome_id=outcome_id,
                actor=actor,
                note=note,
                run_id=run_id,
                created_at_utc=current.isoformat(),
                metadata=meta,
            ))
        state = self._read_state()
        run_state_mut = _safe_mapping(state.get("run_state"))
        if str(run_state_mut.get("run_id") or "") == run_id:
            run_state_mut["pending_transition"] = {}
            checkpoints = list(run_state_mut.get("checkpoints") or [])
            checkpoints.append({"name": f"resume:{operation}", "at_utc": current.isoformat()})
            linked = list(run_state_mut.get("linked_outcome_ids") or [])
            if outcome_id and outcome_id not in linked:
                linked.append(outcome_id)
            run_state_mut["linked_outcome_ids"] = linked
            run_state_mut["checkpoints"] = checkpoints
            state["run_state"] = run_state_mut
            self._write_state(state)
        return True

    def _read_state(self) -> dict[str, Any]:
        if not self.state_path.exists():
            return {"active": {}, "resolved": {}, "quarantined": {}, "run_state": {}}
        try:
            payload = json.loads(self.state_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {"active": {}, "resolved": {}, "quarantined": {}, "run_state": {}}
        if not isinstance(payload, dict):
            return {"active": {}, "resolved": {}, "quarantined": {}, "run_state": {}}
        return {
            "active": _safe_mapping(payload.get("active")),
            "resolved": _safe_mapping(payload.get("resolved")),
            "quarantined": _safe_mapping(payload.get("quarantined")),
            "run_state": _safe_mapping(payload.get("run_state")),
        }

    def _write_state(self, state: Mapping[str, Any]) -> None:
        payload = {
            "active": _safe_mapping(state.get("active")),
            "resolved": _safe_mapping(state.get("resolved")),
            "quarantined": _safe_mapping(state.get("quarantined")),
            "run_state": _safe_mapping(state.get("run_state")),
        }
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp_name = tempfile.mkstemp(prefix=self.state_path.name + ".", suffix=".tmp", dir=str(self.state_path.parent))
        tmp_path = Path(tmp_name)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                json.dump(payload, fh, ensure_ascii=False, indent=2, sort_keys=True)
                fh.flush()
                os.fsync(fh.fileno())
            tmp_path.replace(self.state_path)
        finally:
            if tmp_path.exists():
                with suppress(OSError):
                    tmp_path.unlink()


__all__ = [
    "BusinessAutonomyDelayedOutcomeBridge",
    "BusinessDelayedOutcomeReference",
    "DelayedOutcomeSweepResult",
    "DelayedOutcomeSweepRunRecord",
    "DelayedOutcomeActionRecord",
    "BusinessDelayedOutcomeQuarantineEntry",
    "business_autonomy_delayed_outcome_dir",
    "business_autonomy_delayed_outcome_path",
    "business_autonomy_delayed_outcome_quarantine_path",
    "business_autonomy_delayed_outcome_sweep_journal_path",
    "business_autonomy_delayed_outcome_action_journal_path",
    "business_autonomy_delayed_outcome_action_ledger_path",
    "business_autonomy_delayed_outcome_state_path",
]
