from __future__ import annotations

import json
import os
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any
from collections.abc import Mapping


CANON_STRATEGY_SIGNAL_STORE = True


def _text(value: object) -> str:
    return str(value or '').strip()


def _safe_key(value: object, *, fallback: str) -> str:
    token = _text(value)
    if not token:
        return fallback
    return token.replace('\\', '_').replace('/', '_').replace(':', '_').replace(' ', '_')


@dataclass(frozen=True)
class StrategySignalSnapshot:
    tenant_id: str = ''
    business_id: str = ''
    goal_id: str = ''
    signals: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload['signals'] = list(self.signals)
        return payload

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> 'StrategySignalSnapshot':
        return cls(
            tenant_id=_text(payload.get('tenant_id')),
            business_id=_text(payload.get('business_id')),
            goal_id=_text(payload.get('goal_id')),
            signals=tuple(str(x) for x in (payload.get('signals') or []) if str(x).strip()),
        )


class StrategySignalStore:
    def __init__(self, *, root_dir: Path) -> None:
        self._root_dir = Path(root_dir)
        self._root_dir.mkdir(parents=True, exist_ok=True)

    def _path(self, *, tenant_id: str, business_id: str, goal_id: str) -> Path:
        return self._root_dir / _safe_key(tenant_id, fallback='default') / f"{_safe_key(business_id, fallback='business')}__{_safe_key(goal_id, fallback='goal')}.json"

    def load(self, *, tenant_id: str, business_id: str, goal_id: str) -> StrategySignalSnapshot:
        path = self._path(tenant_id=tenant_id, business_id=business_id, goal_id=goal_id)
        if not path.exists():
            return StrategySignalSnapshot(tenant_id=str(tenant_id), business_id=str(business_id), goal_id=str(goal_id))
        try:
            payload = json.loads(path.read_text(encoding='utf-8'))
        except (OSError, json.JSONDecodeError):
            return StrategySignalSnapshot(tenant_id=str(tenant_id), business_id=str(business_id), goal_id=str(goal_id))
        return StrategySignalSnapshot.from_dict(payload)

    def save(self, snapshot: StrategySignalSnapshot) -> Path:
        path = self._path(tenant_id=snapshot.tenant_id, business_id=snapshot.business_id, goal_id=snapshot.goal_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, temp_name = tempfile.mkstemp(prefix='.strategy_signal_', suffix='.json', dir=str(path.parent))
        try:
            with os.fdopen(fd, 'w', encoding='utf-8') as handle:
                json.dump(snapshot.to_dict(), handle, ensure_ascii=False, indent=2, sort_keys=True)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temp_name, path)
        finally:
            if os.path.exists(temp_name):
                os.unlink(temp_name)
        return path


__all__ = ['CANON_STRATEGY_SIGNAL_STORE', 'StrategySignalSnapshot', 'StrategySignalStore']
