from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Mapping
import json

CANON_DEPLOYMENT_RELEASE_STATE_STORE = True


@dataclass(frozen=True)
class DeploymentStateRecord:
    active_release: str | None = None
    previous_release: str | None = None
    activation_status: str = 'unknown'
    rollback_candidate: str | None = None
    last_successful_health: str | None = None
    applied_profile: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)
    updated_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return {
            'active_release': self.active_release,
            'previous_release': self.previous_release,
            'activation_status': self.activation_status,
            'rollback_candidate': self.rollback_candidate,
            'last_successful_health': self.last_successful_health,
            'applied_profile': self.applied_profile,
            'updated_at': self.updated_at,
            'metadata': dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> 'DeploymentStateRecord':
        metadata = payload.get('metadata')
        return cls(
            active_release=_clean_optional(payload.get('active_release')),
            previous_release=_clean_optional(payload.get('previous_release')),
            activation_status=_clean_required(payload.get('activation_status'), default='unknown'),
            rollback_candidate=_clean_optional(payload.get('rollback_candidate')),
            last_successful_health=_clean_optional(payload.get('last_successful_health')),
            applied_profile=_clean_optional(payload.get('applied_profile')),
            updated_at=_clean_required(payload.get('updated_at'), default=datetime.now(UTC).isoformat()),
            metadata=dict(metadata) if isinstance(metadata, Mapping) else {},
        )


def _clean_optional(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _clean_required(value: Any, *, default: str) -> str:
    text = _clean_optional(value)
    return default if text is None else text


class DeploymentStateStore:
    def __init__(self, path: str | Path = 'data/deployment/release_state.json') -> None:
        self._path = Path(path)

    @property
    def path(self) -> Path:
        return self._path

    def load(self) -> DeploymentStateRecord:
        if not self._path.exists():
            return DeploymentStateRecord()
        payload = json.loads(self._path.read_text(encoding='utf-8'))
        if not isinstance(payload, Mapping):
            raise TypeError('deployment state file must contain a JSON object')
        return DeploymentStateRecord.from_dict(payload)

    def save(self, record: DeploymentStateRecord) -> DeploymentStateRecord:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = self._path.with_suffix(self._path.suffix + '.tmp')
        temp_path.write_text(json.dumps(record.to_dict(), ensure_ascii=False, indent=2, sort_keys=True) + '\n', encoding='utf-8')
        temp_path.replace(self._path)
        return record

    def update(self, **fields: Any) -> DeploymentStateRecord:
        current = self.load()
        payload = current.to_dict()
        next_active_release = _clean_optional(fields.get('active_release', payload.get('active_release')))
        if 'previous_release' not in fields and current.active_release is not None and next_active_release != current.active_release:
            payload['previous_release'] = current.active_release
        payload.update(fields)
        payload['updated_at'] = datetime.now(UTC).isoformat()
        record = DeploymentStateRecord.from_dict(payload)
        self.save(record)
        return record


__all__ = [
    'CANON_DEPLOYMENT_RELEASE_STATE_STORE',
    'DeploymentStateRecord',
    'DeploymentStateStore',
]
