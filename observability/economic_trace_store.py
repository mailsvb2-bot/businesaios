from __future__ import annotations

CANON_COMPAT_SHIM = True

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Mapping, Protocol


CANON_ECONOMIC_TRACE_STORE = True


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()


def _safe_dict(value: object) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _safe_float(value: object, *, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _safe_bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return bool(value)


def _text(value: object) -> str:
    return str(value or "").strip()


@dataclass(frozen=True, slots=True)
class EconomicTraceRecord:
    trace_id: str
    action_type: str
    channel: str
    survival_mode: str
    budget_allowed: bool
    operator_required: bool
    requested_budget: float
    approved_budget: float
    revenue_verified: bool
    revenue_amount: float
    created_at: str = field(default_factory=_utc_now)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "trace_id": self.trace_id,
            "action_type": self.action_type,
            "channel": self.channel,
            "survival_mode": self.survival_mode,
            "budget_allowed": bool(self.budget_allowed),
            "operator_required": bool(self.operator_required),
            "requested_budget": float(self.requested_budget),
            "approved_budget": float(self.approved_budget),
            "revenue_verified": bool(self.revenue_verified),
            "revenue_amount": float(self.revenue_amount),
            "created_at": self.created_at,
            "metadata": dict(self.metadata),
        }


class EconomicTraceStore(Protocol):
    @property
    def path(self) -> Path: ...

    def append(self, row: EconomicTraceRecord) -> None: ...
    def append_from_results(
        self,
        *,
        trace_id: str,
        action_type: str,
        budget_guard_result: Mapping[str, Any] | None,
        revenue_verification_result: Mapping[str, Any] | None,
        planning_signals: Mapping[str, Any] | None = None,
    ) -> EconomicTraceRecord: ...
    def list_rows(self) -> tuple[EconomicTraceRecord, ...]: ...


class NoOpEconomicTraceStore:
    def append(self, row: EconomicTraceRecord) -> None:
        return None

    def list_rows(self) -> tuple[EconomicTraceRecord, ...]:
        return ()

    def append_from_results(
        self,
        *,
        trace_id: str,
        action_type: str,
        budget_guard_result: Mapping[str, Any] | None,
        revenue_verification_result: Mapping[str, Any] | None,
        planning_signals: Mapping[str, Any] | None = None,
    ) -> EconomicTraceRecord:
        return build_economic_trace_record(
            trace_id=trace_id,
            action_type=action_type,
            budget_guard_result=budget_guard_result,
            revenue_verification_result=revenue_verification_result,
            planning_signals=planning_signals,
        )


class InMemoryEconomicTraceStore:
    def __init__(self) -> None:
        self._rows: list[EconomicTraceRecord] = []

    def append(self, row: EconomicTraceRecord) -> None:
        self._rows.append(row)

    def list_rows(self) -> tuple[EconomicTraceRecord, ...]:
        return tuple(self._rows)

    def append_from_results(
        self,
        *,
        trace_id: str,
        action_type: str,
        budget_guard_result: Mapping[str, Any] | None,
        revenue_verification_result: Mapping[str, Any] | None,
        planning_signals: Mapping[str, Any] | None = None,
    ) -> EconomicTraceRecord:
        row = build_economic_trace_record(
            trace_id=trace_id,
            action_type=action_type,
            budget_guard_result=budget_guard_result,
            revenue_verification_result=revenue_verification_result,
            planning_signals=planning_signals,
        )
        self.append(row)
        return row


class JsonlEconomicTraceStore:
    def __init__(self, path: str | Path) -> None:
        self._path = Path(path)

    @property
    def path(self) -> Path:
        return self._path

    def append(self, row: EconomicTraceRecord) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with self._path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(row.to_dict(), ensure_ascii=False, sort_keys=True))
            handle.write("\n")

    def append_from_results(
        self,
        *,
        trace_id: str,
        action_type: str,
        budget_guard_result: Mapping[str, Any] | None,
        revenue_verification_result: Mapping[str, Any] | None,
        planning_signals: Mapping[str, Any] | None = None,
    ) -> EconomicTraceRecord:
        row = build_economic_trace_record(
            trace_id=trace_id,
            action_type=action_type,
            budget_guard_result=budget_guard_result,
            revenue_verification_result=revenue_verification_result,
            planning_signals=planning_signals,
        )
        self.append(row)
        return row

    def list_rows(self) -> tuple[EconomicTraceRecord, ...]:
        if not self._path.exists():
            return ()
        rows: list[EconomicTraceRecord] = []
        with self._path.open('r', encoding='utf-8') as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                payload = _safe_dict(json.loads(line))
                rows.append(EconomicTraceRecord(
                    trace_id=_text(payload.get('trace_id')),
                    action_type=_text(payload.get('action_type')),
                    channel=_text(payload.get('channel')),
                    survival_mode=_text(payload.get('survival_mode')),
                    budget_allowed=_safe_bool(payload.get('budget_allowed')),
                    operator_required=_safe_bool(payload.get('operator_required')),
                    requested_budget=_safe_float(payload.get('requested_budget')),
                    approved_budget=_safe_float(payload.get('approved_budget')),
                    revenue_verified=_safe_bool(payload.get('revenue_verified')),
                    revenue_amount=_safe_float(payload.get('revenue_amount')),
                    created_at=_text(payload.get('created_at')),
                    metadata=_safe_dict(payload.get('metadata')),
                ))
        return tuple(rows)


def build_economic_trace_record(
    *,
    trace_id: str,
    action_type: str,
    budget_guard_result: Mapping[str, Any] | None,
    revenue_verification_result: Mapping[str, Any] | None,
    planning_signals: Mapping[str, Any] | None = None,
) -> EconomicTraceRecord:
    budget_payload = _safe_dict(budget_guard_result)
    budget_meta = _safe_dict(budget_payload.get("metadata"))
    spend_limits = _safe_dict(budget_payload.get("spend_limits"))
    revenue_payload = _safe_dict(revenue_verification_result)

    resolved_signals = _safe_dict(planning_signals) or _safe_dict(budget_meta.get("planning_signals"))

    return EconomicTraceRecord(
        trace_id=_text(trace_id),
        action_type=_text(action_type),
        channel=_text(resolved_signals.get("channel") or budget_meta.get("channel") or "default"),
        survival_mode=_text(resolved_signals.get("survival_mode") or "normal"),
        budget_allowed=_safe_bool(budget_payload.get("allowed")),
        operator_required=_safe_bool(
            resolved_signals.get("operator_required")
            if "operator_required" in resolved_signals
            else budget_payload.get("operator_required")
        ),
        requested_budget=_safe_float(
            resolved_signals.get("requested_budget"),
            default=_safe_float(spend_limits.get("requested_budget")),
        ),
        approved_budget=_safe_float(
            resolved_signals.get("approved_budget"),
            default=_safe_float(spend_limits.get("approved_budget")),
        ),
        revenue_verified=_safe_bool(revenue_payload.get("verified")),
        revenue_amount=_safe_float(revenue_payload.get("revenue_amount")),
        metadata={
            "owner": "observability.economic_trace_store",
            "corrupted": bool(_safe_dict(revenue_verification_result).get("verification_status") == "corrupted_bundle"),
            "scope_drift": bool(_safe_dict(planning_signals).get("scope_drift", False)),
        },
    )


__all__ = [
    "CANON_ECONOMIC_TRACE_STORE",
    "EconomicTraceRecord",
    "EconomicTraceStore",
    "NoOpEconomicTraceStore",
    "InMemoryEconomicTraceStore",
    "JsonlEconomicTraceStore",
    "build_economic_trace_record",
]
