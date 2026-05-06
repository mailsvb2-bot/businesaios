from __future__ import annotations

from dataclasses import dataclass, field, is_dataclass, replace
from datetime import UTC, datetime
from typing import Any, Mapping, MutableMapping

from application.effects.canonical_execution_feedback import canonical_execution_feedback, canonical_world_state_row


CANON_WORLD_STATE_UPDATER = True


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _safe_dict(value: object) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return dict(value)
    return {}


def _ensure_mapping(value: object) -> dict[str, Any]:
    if isinstance(value, MutableMapping):
        return dict(value)
    if isinstance(value, Mapping):
        return dict(value)
    return {}


def _get_meta(world_state: object) -> dict[str, Any]:
    return _safe_dict(getattr(world_state, "meta", {}))


def _safe_list(value: object, *, limit: int = 8) -> list[str]:
    if isinstance(value, (list, tuple, set)):
        items = [str(item).strip() for item in value if str(item).strip()]
        return items[:limit]
    text = str(value or '').strip()
    return [text] if text else []


def _sanitize_history_row(row: Mapping[str, Any], *, updated_at: str) -> dict[str, Any]:
    external_refs = _safe_list(row.get('external_refs') or row.get('external_ref'))
    sanitized = {
        'action_type': str(row.get('action_type') or '').strip(),
        'action_id': str(row.get('action_id') or '').strip(),
        'decision_id': str(row.get('decision_id') or '').strip(),
        'correlation_id': str(row.get('correlation_id') or '').strip(),
        'verified': bool(row.get('verified', False)),
        'verification_status': str(row.get('verification_status') or row.get('status') or '').strip(),
        'message': str(row.get('message') or '').strip()[:256],
        'external_refs': external_refs,
        'external_ref': external_refs[0] if external_refs else str(row.get('external_ref') or '').strip(),
        'source_of_truth': str(row.get('source_of_truth') or row.get('verification_source') or '').strip(),
        'attempted': bool(row.get('attempted', False)),
        'executed': bool(row.get('executed', False)),
        'operator_required': bool(row.get('operator_required', False)),
        'retryable': bool(row.get('retryable', False)),
        'matched_records': int(row.get('matched_records') or 0),
        'total_records': int(row.get('total_records') or 0),
        'updated_at': str(row.get('updated_at') or updated_at).strip() or updated_at,
    }
    return sanitized


def _history_row_key(row: Mapping[str, Any]) -> tuple[str, str, str, str, str, str]:
    return (
        str(row.get("action_type") or ""),
        str(row.get("action_id") or ""),
        str(row.get("decision_id") or ""),
        str(row.get("correlation_id") or ""),
        str(row.get("verification_status") or row.get("status") or ""),
        str(row.get("external_ref") or ""),
    )


def _compact_history(history: list[dict[str, Any]], *, limit: int) -> list[dict[str, Any]]:
    deduped: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str, str, str, str]] = set()
    for item in history:
        row = _safe_dict(item)
        if not row:
            continue
        key = _history_row_key(row)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(row)
        if len(deduped) >= limit:
            break
    return deduped


def _recent_actions(history: list[dict[str, Any]], *, limit: int) -> list[str]:
    actions: list[str] = []
    seen: set[str] = set()
    for item in history:
        action = str(item.get("action_type") or "").strip()
        if not action or action in seen:
            continue
        seen.add(action)
        actions.append(action)
        if len(actions) >= limit:
            break
    return actions


@dataclass(frozen=True, slots=True)
class WorldStateUpdate:
    updated_at: str
    meta_patch: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {"updated_at": self.updated_at, "meta_patch": dict(self.meta_patch)}


class WorldStateUpdater:
    def build_update(
        self,
        *,
        verification_result: Mapping[str, Any] | None,
        action: Mapping[str, Any] | None = None,
    ) -> WorldStateUpdate:
        verification_payload = _safe_dict(verification_result)
        action_payload = _safe_dict(action)
        verification_block = _safe_dict(verification_payload.get("verification"))
        outcome_block = _safe_dict(verification_block.get("outcome"))
        snapshot = canonical_execution_feedback(verification_result=verification_payload, action=action_payload)
        updated_at = _utc_now().isoformat()

        row = _sanitize_history_row(canonical_world_state_row(snapshot), updated_at=updated_at)
        row["matched_records"] = int(outcome_block.get("matched_records") or 0)
        row["total_records"] = int(outcome_block.get("total_records") or 0)
        row["verification_source"] = str(verification_block.get("source_of_truth") or row.get("source_of_truth") or "")
        external_refs = verification_block.get("external_refs") or verification_payload.get("external_refs") or []
        row["external_refs"] = _safe_list(external_refs)
        row["external_ref"] = row["external_refs"][0] if row["external_refs"] else ""
        return WorldStateUpdate(
            updated_at=updated_at,
            meta_patch={
                "execution_closed_loop": {
                    "last_verification": row,
                    "append_history": row,
                }
            },
        )

    def apply(self, *, world_state: Any, update: WorldStateUpdate) -> Any:
        if isinstance(world_state, MutableMapping):
            state = dict(world_state)
            meta = _ensure_mapping(state.get("meta"))
            state["meta"] = self._apply_meta(meta, update)
            return state
        if is_dataclass(world_state):
            return replace(world_state, meta=self._apply_meta(_get_meta(world_state), update))
        return {"meta": self._apply_meta({}, update)}

    def _apply_meta(self, meta: dict[str, Any], update: WorldStateUpdate) -> dict[str, Any]:
        current = dict(meta)
        execution_closed_loop = _ensure_mapping(current.get("execution_closed_loop"))
        patch = _safe_dict(update.meta_patch.get("execution_closed_loop"))
        new_row = _sanitize_history_row(_safe_dict(patch.get("append_history")), updated_at=update.updated_at) if patch.get("append_history") else {}
        history = [dict(item or {}) for item in execution_closed_loop.get("execution_history") or []]
        merged_history = _compact_history(([new_row] if new_row else []) + history, limit=20)
        recent_window = merged_history[:10]
        sanitized_last_verification = _sanitize_history_row(
            _safe_dict(patch.get("last_verification")),
            updated_at=update.updated_at,
        ) if patch.get("last_verification") else _safe_dict(execution_closed_loop.get("last_verification"))
        execution_closed_loop.update(
            {
                "updated_at": update.updated_at,
                "last_verification": sanitized_last_verification,
                "execution_history": merged_history,
                "recent_verified_runs": sum(1 for item in recent_window if item.get("verified")),
                "recent_failed_runs": sum(1 for item in recent_window if item and not item.get("verified")),
                "recent_actions": _recent_actions(recent_window, limit=5),
            }
        )
        current["execution_closed_loop"] = execution_closed_loop
        return current


__all__ = ["CANON_WORLD_STATE_UPDATER", "WorldStateUpdate", "WorldStateUpdater"]
