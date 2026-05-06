from __future__ import annotations

import json
import os
import tempfile
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Mapping


CANON_RETRY_LEARNING_STORE = True


def _text(value: object) -> str:
    return str(value or '').strip()


def _safe_int(value: object, *, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return int(default)


def _safe_key(value: object, *, fallback: str) -> str:
    token = _text(value)
    if not token:
        return fallback
    return token.replace('\\', '_').replace('/', '_').replace(':', '_').replace(' ', '_')


@dataclass(frozen=True)
class RetryLearningSnapshot:
    tenant_id: str = ''
    action_type: str = ''
    error_family: str = 'unknown'
    attempts: int = 0
    successes_after_retry: int = 0
    last_backoff_seconds: int = 0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> 'RetryLearningSnapshot':
        return cls(
            tenant_id=_text(payload.get('tenant_id')),
            action_type=_text(payload.get('action_type')),
            error_family=_text(payload.get('error_family') or 'unknown') or 'unknown',
            attempts=max(0, _safe_int(payload.get('attempts'))),
            successes_after_retry=max(0, _safe_int(payload.get('successes_after_retry'))),
            last_backoff_seconds=max(0, _safe_int(payload.get('last_backoff_seconds'))),
        )


class RetryLearningStore:
    def __init__(self, *, root_dir: Path) -> None:
        self._root_dir = Path(root_dir)
        self._root_dir.mkdir(parents=True, exist_ok=True)

    def _path(self, *, tenant_id: str, action_type: str, error_family: str) -> Path:
        return self._root_dir / _safe_key(tenant_id, fallback='default') / f"{_safe_key(action_type, fallback='action')}__{_safe_key(error_family, fallback='unknown')}.json"

    def load(self, *, tenant_id: str, action_type: str, error_family: str) -> RetryLearningSnapshot:
        path = self._path(tenant_id=tenant_id, action_type=action_type, error_family=error_family)
        if not path.exists():
            return RetryLearningSnapshot(tenant_id=str(tenant_id), action_type=str(action_type), error_family=str(error_family))
        try:
            payload = json.loads(path.read_text(encoding='utf-8'))
        except (OSError, json.JSONDecodeError):
            return RetryLearningSnapshot(tenant_id=str(tenant_id), action_type=str(action_type), error_family=str(error_family))
        return RetryLearningSnapshot.from_dict(payload)

    def save(self, snapshot: RetryLearningSnapshot) -> Path:
        path = self._path(tenant_id=snapshot.tenant_id, action_type=snapshot.action_type, error_family=snapshot.error_family)
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, temp_name = tempfile.mkstemp(prefix='.retry_learning_', suffix='.json', dir=str(path.parent))
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


__all__ = ['CANON_RETRY_LEARNING_STORE', 'RetryLearningSnapshot', 'RetryLearningStore']
