from __future__ import annotations

import json
import os
import tempfile
from dataclasses import asdict, dataclass, field
from pathlib import Path
from threading import RLock

from core.safety.operational.operational_budget_ledger import OperationalBudgetCounters


CANON_PERSISTENT_OPERATIONAL_BUDGET_LEDGER = True


@dataclass
class _PersistentLedgerState:
    hourly: dict[str, dict[str, int]] = field(default_factory=dict)
    daily: dict[str, dict[str, int]] = field(default_factory=dict)
    committed_execution_ids: list[str] = field(default_factory=list)


class OperationalLedgerLoadError(RuntimeError):
    pass


class PersistentOperationalBudgetLedger:
    """
    File-backed canonical ledger.

    Guarantees:
    - fail-closed loading on malformed persisted state;
    - tenant-scoped idempotent commit via execution_id;
    - durable counters across process restarts;
    - atomic writes through temp file + replace;
    - bounded idempotency state growth via pruning.
    """

    def __init__(self, storage_path: str | Path) -> None:
        self._storage_path = Path(storage_path)
        self._lock = RLock()
        self._hourly: dict[tuple[str, str], OperationalBudgetCounters] = {}
        self._daily: dict[tuple[str, str], OperationalBudgetCounters] = {}
        self._committed_execution_ids: set[str] = set()
        self._load()

    def get_hour(self, tenant_id: str, hour_bucket: str) -> OperationalBudgetCounters:
        with self._lock:
            return self._hourly.get((str(tenant_id), str(hour_bucket)), OperationalBudgetCounters())

    def get_day(self, tenant_id: str, day_bucket: str) -> OperationalBudgetCounters:
        with self._lock:
            return self._daily.get((str(tenant_id), str(day_bucket)), OperationalBudgetCounters())

    def commit(
        self,
        tenant_id: str,
        *,
        execution_id: str | None,
        hour_bucket: str,
        day_bucket: str,
        actions_count: int,
        budget_minor: int,
        publications_count: int,
        outbound_count: int,
        strategic_changes_without_approval: int,
        rollback_triggers: int,
    ) -> None:
        with self._lock:
            normalized_execution_id = self._execution_identity(tenant_id, execution_id)
            if normalized_execution_id is not None:
                if normalized_execution_id in self._committed_execution_ids:
                    return

            hour_key = (str(tenant_id), str(hour_bucket))
            day_key = (str(tenant_id), str(day_bucket))

            self._hourly[hour_key] = self._merge(
                self._hourly.get(hour_key, OperationalBudgetCounters()),
                actions_count=actions_count,
            )
            self._daily[day_key] = self._merge(
                self._daily.get(day_key, OperationalBudgetCounters()),
                actions_count=actions_count,
                budget_minor=budget_minor,
                publications_count=publications_count,
                outbound_count=outbound_count,
                strategic_changes_without_approval=strategic_changes_without_approval,
                rollback_triggers=rollback_triggers,
            )

            if normalized_execution_id is not None:
                self._committed_execution_ids.add(normalized_execution_id)
                self._prune_execution_ids(max_size=100_000)

            self._flush()

    def _load(self) -> None:
        with self._lock:
            if not self._storage_path.exists():
                self._storage_path.parent.mkdir(parents=True, exist_ok=True)
                return

            try:
                raw = json.loads(self._storage_path.read_text(encoding="utf-8"))
                if not isinstance(raw, dict):
                    raise ValueError("persistent ledger file must contain a JSON object")

                state = _PersistentLedgerState(
                    hourly=dict(raw.get("hourly") or {}),
                    daily=dict(raw.get("daily") or {}),
                    committed_execution_ids=list(raw.get("committed_execution_ids") or []),
                )

                self._hourly = {
                    self._decode_key(key): self._decode_counters(value)
                    for key, value in state.hourly.items()
                }
                self._daily = {
                    self._decode_key(key): self._decode_counters(value)
                    for key, value in state.daily.items()
                }
                self._committed_execution_ids = {
                    str(item).strip()
                    for item in state.committed_execution_ids
                    if str(item).strip()
                }
            except Exception as exc:  # noqa: BLE001
                raise OperationalLedgerLoadError(
                    f"failed to load persistent operational budget ledger: {self._storage_path}"
                ) from exc

    def _flush(self) -> None:
        self._storage_path.parent.mkdir(parents=True, exist_ok=True)
        state = _PersistentLedgerState(
            hourly={self._encode_key(key): asdict(value) for key, value in self._hourly.items()},
            daily={self._encode_key(key): asdict(value) for key, value in self._daily.items()},
            committed_execution_ids=sorted(self._committed_execution_ids),
        )
        payload = json.dumps(asdict(state), ensure_ascii=False, sort_keys=True, indent=2)

        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=str(self._storage_path.parent),
            delete=False,
        ) as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
            temp_path = handle.name

        os.replace(temp_path, self._storage_path)

    @staticmethod
    def _encode_key(key: tuple[str, str]) -> str:
        tenant_id, bucket = key
        return json.dumps([tenant_id, bucket], ensure_ascii=False, separators=(",", ":"))

    @staticmethod
    def _decode_key(raw: str) -> tuple[str, str]:
        parsed = json.loads(str(raw))
        if not isinstance(parsed, list) or len(parsed) != 2:
            raise ValueError(f"invalid persistent ledger key: {raw!r}")
        tenant_id, bucket = parsed
        return str(tenant_id), str(bucket)

    @staticmethod
    def _execution_identity(tenant_id: str, execution_id: str | None) -> str | None:
        if execution_id is None:
            return None
        normalized_execution_id = str(execution_id).strip()
        if not normalized_execution_id:
            return None
        return json.dumps(
            [str(tenant_id).strip(), normalized_execution_id],
            ensure_ascii=False,
            separators=(",", ":"),
        )

    def _prune_execution_ids(self, max_size: int) -> None:
        if len(self._committed_execution_ids) <= int(max_size):
            return
        trimmed = sorted(self._committed_execution_ids)[-int(max_size):]
        self._committed_execution_ids = set(trimmed)

    @staticmethod
    def _decode_counters(raw: dict[str, int]) -> OperationalBudgetCounters:
        data = dict(raw or {})
        return OperationalBudgetCounters(
            actions_count=max(0, int(data.get("actions_count", 0))),
            budget_minor=max(0, int(data.get("budget_minor", 0))),
            publications_count=max(0, int(data.get("publications_count", 0))),
            outbound_count=max(0, int(data.get("outbound_count", 0))),
            strategic_changes_without_approval=max(
                0,
                int(data.get("strategic_changes_without_approval", 0)),
            ),
            rollback_triggers=max(0, int(data.get("rollback_triggers", 0))),
        )

    @staticmethod
    def _merge(
        base: OperationalBudgetCounters,
        *,
        actions_count: int = 0,
        budget_minor: int = 0,
        publications_count: int = 0,
        outbound_count: int = 0,
        strategic_changes_without_approval: int = 0,
        rollback_triggers: int = 0,
    ) -> OperationalBudgetCounters:
        return OperationalBudgetCounters(
            actions_count=int(base.actions_count) + int(actions_count),
            budget_minor=int(base.budget_minor) + int(budget_minor),
            publications_count=int(base.publications_count) + int(publications_count),
            outbound_count=int(base.outbound_count) + int(outbound_count),
            strategic_changes_without_approval=(
                int(base.strategic_changes_without_approval) + int(strategic_changes_without_approval)
            ),
            rollback_triggers=int(base.rollback_triggers) + int(rollback_triggers),
        )


__all__ = [
    "OperationalLedgerLoadError",
    "PersistentOperationalBudgetLedger",
]