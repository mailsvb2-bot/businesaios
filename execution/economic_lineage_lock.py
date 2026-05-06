from __future__ import annotations

from dataclasses import dataclass, field
from hashlib import sha256
from typing import Any, Mapping
import json

CANON_ECONOMIC_LINEAGE_LOCK = True


def _safe_dict(value: object) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _text(value: object) -> str:
    return str(value or '').strip()


def _stable_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'))


@dataclass(frozen=True, slots=True)
class EconomicLineageLockVerdict:
    valid: bool
    lineage_hash: str
    parent_count: int
    fork_detected: bool
    reason: str = 'economic_lineage_lock_valid'
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            'valid': bool(self.valid),
            'lineage_hash': self.lineage_hash,
            'parent_count': int(self.parent_count),
            'fork_detected': bool(self.fork_detected),
            'reason': self.reason,
            'metadata': dict(self.metadata),
        }


class EconomicLineageLockBuilder:
    def build_hash(self, *, scope: Mapping[str, Any] | None, scope_lineage: Mapping[str, Any] | None) -> str:
        payload = {
            'scope': _safe_dict(scope),
            'scope_lineage': _safe_dict(scope_lineage),
        }
        return sha256(_stable_json(payload).encode('utf-8')).hexdigest()

    def validate(self, *, manifest: Mapping[str, Any], expected_scope: Mapping[str, Any] | None = None) -> EconomicLineageLockVerdict:
        normalized = _safe_dict(manifest)
        scope = _safe_dict(normalized.get('scope'))
        scope_lineage = _safe_dict(normalized.get('scope_lineage'))
        lineage_lock = _safe_dict(normalized.get('lineage_lock'))
        parents = lineage_lock.get('parents') or scope_lineage.get('parents') or []
        parent_count = len([p for p in parents if _safe_dict(p)])
        fork_detected = parent_count > 1
        expected_hash = self.build_hash(scope=scope, scope_lineage=scope_lineage)
        provided_hash = _text(lineage_lock.get('lineage_hash')) or _text(normalized.get('scope_lineage_digest'))
        valid = bool(provided_hash) and provided_hash == expected_hash and not fork_detected
        reason = 'economic_lineage_lock_valid'
        if fork_detected:
            reason = 'economic_lineage_fork_detected'
        elif not provided_hash or provided_hash != expected_hash:
            reason = 'economic_lineage_hash_mismatch'
        if expected_scope:
            exp = _safe_dict(expected_scope)
            for key in ('tenant_id', 'business_id'):
                if _text(exp.get(key)) and _text(scope.get(key)) and _text(exp.get(key)) != _text(scope.get(key)):
                    valid = False
                    reason = 'economic_lineage_scope_mismatch'
                    break
        return EconomicLineageLockVerdict(
            valid=valid,
            lineage_hash=provided_hash or expected_hash,
            parent_count=parent_count,
            fork_detected=fork_detected,
            reason=reason,
            metadata={'owner': 'execution.economic_lineage_lock'},
        )


__all__ = [
    'CANON_ECONOMIC_LINEAGE_LOCK',
    'EconomicLineageLockVerdict',
    'EconomicLineageLockBuilder',
]
