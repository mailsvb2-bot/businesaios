from __future__ import annotations

from execution.runtime_keys import ACTION_BUDGET_KEY
from dataclasses import dataclass
from typing import Any
from collections.abc import Iterable, Mapping


CANON_RECENT_ACTIONS = True
DEFAULT_RECENT_ACTION_LIMIT = 50


@dataclass(frozen=True)
class RecentActionSummary:
    action_type: str
    status: str
    executed: bool
    verified: bool
    operator_required: bool
    outbound_count: int = 0
    publication_count: int = 0
    irreversible_count: int = 0
    budget_change_amount: float = 0.0
    step_index: int | None = None
    decision_id: str | None = None
    action_id: str | None = None
    run_id: str | None = None
    recorded_at: str | None = None

    def dedupe_key(self) -> str:
        if self.action_id:
            return f"action:{self.action_id}"
        if self.decision_id:
            return f"decision:{self.decision_id}"
        base = [self.action_type, self.status, str(self.step_index or 0), str(self.run_id or "")]
        return "|".join(base)

    def to_dict(self) -> dict[str, Any]:
        return {
            "action_type": str(self.action_type),
            "status": str(self.status),
            "executed": bool(self.executed),
            "verified": bool(self.verified),
            "operator_required": bool(self.operator_required),
            "outbound_count": int(self.outbound_count),
            "publication_count": int(self.publication_count),
            "irreversible_count": int(self.irreversible_count),
            "budget_change_amount": float(self.budget_change_amount),
            "step_index": self.step_index,
            "decision_id": self.decision_id,
            "action_id": self.action_id,
            "run_id": self.run_id,
            "recorded_at": self.recorded_at,
        }


class RecentActionsSource:
    def __init__(self, *, max_items: int = DEFAULT_RECENT_ACTION_LIMIT) -> None:
        self._max_items = max(1, int(max_items))

    @staticmethod
    def _safe_int(value: object, *, default: int = 0) -> int:
        try:
            return int(value)
        except (TypeError, ValueError):
            return int(default)

    @staticmethod
    def _safe_float(value: object, *, default: float = 0.0) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return float(default)

    @staticmethod
    def _safe_dict(value: object) -> dict[str, Any]:
        if isinstance(value, Mapping):
            return dict(value)
        return {}

    def summary_from_step(self, *, step: Any, run_id: str | None = None) -> RecentActionSummary:
        feedback = self._safe_dict(getattr(step, "feedback", {}) or {})
        budget = self._safe_dict(feedback.get(ACTION_BUDGET_KEY) or {})
        cost = self._safe_dict(budget.get("cost") or {})
        return RecentActionSummary(
            action_type=str(getattr(step, "action", "") or ""),
            status=str(getattr(step, "status", "") or ""),
            executed=bool(getattr(step, "executed", False)),
            verified=bool(getattr(step, "verified", False)),
            operator_required=bool(getattr(step, "operator_required", False)),
            outbound_count=max(0, self._safe_int(cost.get("outbound_count"))),
            publication_count=max(0, self._safe_int(cost.get("publication_count"))),
            irreversible_count=max(0, self._safe_int(cost.get("irreversible_count"))),
            budget_change_amount=max(0.0, self._safe_float(cost.get("budget_change_amount"))),
            step_index=getattr(step, "step_index", None),
            decision_id=str(feedback.get("decision_id") or getattr(step, "decision_id", "") or "") or None,
            action_id=str(feedback.get("action_id") or getattr(step, "action_id", "") or "") or None,
            run_id=str(run_id or "") or None,
            recorded_at=str(feedback.get("recorded_at") or "") or None,
        )

    def normalize(self, items: Iterable[object] | None) -> list[dict[str, Any]]:
        normalized: list[dict[str, Any]] = []
        seen: set[str] = set()
        for raw in list(items or []):
            if isinstance(raw, RecentActionSummary):
                summary = raw
            else:
                item = self._safe_dict(raw)
                summary = RecentActionSummary(
                    action_type=str(item.get("action_type") or ""),
                    status=str(item.get("status") or ""),
                    executed=bool(item.get("executed", False)),
                    verified=bool(item.get("verified", False)),
                    operator_required=bool(item.get("operator_required", False)),
                    outbound_count=max(0, self._safe_int(item.get("outbound_count"))),
                    publication_count=max(0, self._safe_int(item.get("publication_count"))),
                    irreversible_count=max(0, self._safe_int(item.get("irreversible_count"))),
                    budget_change_amount=max(0.0, self._safe_float(item.get("budget_change_amount"))),
                    step_index=item.get("step_index") if item.get("step_index") is None else self._safe_int(item.get("step_index")),
                    decision_id=str(item.get("decision_id") or "") or None,
                    action_id=str(item.get("action_id") or "") or None,
                    run_id=str(item.get("run_id") or "") or None,
                    recorded_at=str(item.get("recorded_at") or "") or None,
                )
            dedupe_key = summary.dedupe_key()
            if dedupe_key in seen:
                continue
            seen.add(dedupe_key)
            normalized.append(summary.to_dict())
        return normalized[: self._max_items]

    def append(self, *, history: Iterable[object] | None, summary: RecentActionSummary | Mapping[str, Any]) -> list[dict[str, Any]]:
        rows = self.normalize(history)
        rows.insert(0, dict(summary.to_dict() if isinstance(summary, RecentActionSummary) else dict(summary)))
        return self.normalize(rows)


__all__ = [
    "CANON_RECENT_ACTIONS",
    "DEFAULT_RECENT_ACTION_LIMIT",
    "RecentActionSummary",
    "RecentActionsSource",
]
