from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

CANON_ECONOMIC_SCOPE_LINEAGE = True


def _safe_dict(value: object) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _text(value: object) -> str:
    return str(value or '').strip()


def _scope_key(payload: Mapping[str, Any]) -> str:
    normalized = _safe_dict(payload)
    return '::'.join(
        [
            _text(normalized.get('tenant_id')),
            _text(normalized.get('business_id')),
            _text(normalized.get('tenant_tier')),
            _text(normalized.get('business_tier')),
        ]
    )


def _profile_name(payload: Mapping[str, Any]) -> str:
    return _text(_safe_dict(payload).get('profile_name'))


@dataclass(frozen=True, slots=True)
class EconomicScopeLineageVerdict:
    lineage_clear: bool
    old_scope_key: str
    new_scope_key: str
    migration_allowed: bool
    decision_class: str
    reason: str
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            'lineage_clear': bool(self.lineage_clear),
            'old_scope_key': self.old_scope_key,
            'new_scope_key': self.new_scope_key,
            'migration_allowed': bool(self.migration_allowed),
            'decision_class': self.decision_class,
            'reason': self.reason,
            'metadata': dict(self.metadata),
        }


class EconomicScopeLineageGuard:
    def validate(
        self,
        *,
        current_scope: Mapping[str, Any] | None,
        incoming_scope: Mapping[str, Any] | None,
        declared_lineage: Mapping[str, Any] | None = None,
    ) -> EconomicScopeLineageVerdict:
        current = _safe_dict(current_scope)
        incoming = _safe_dict(incoming_scope)
        current_key = _scope_key(current)
        incoming_key = _scope_key(incoming)
        lineage = _safe_dict(declared_lineage)
        declared_old = _scope_key(_safe_dict(lineage.get('old_scope')))
        declared_new = _scope_key(_safe_dict(lineage.get('new_scope')))
        declared_mode = _text(lineage.get('mode')).lower()
        review_state = _text(lineage.get('review_state')).lower()
        integrity_state = _text(lineage.get('integrity_state') or incoming.get('integrity_state')).lower()
        source_status = _text(lineage.get('source_status') or incoming.get('source_status')).lower()
        profile_changed = bool(_profile_name(current) and _profile_name(incoming) and _profile_name(current) != _profile_name(incoming))

        if integrity_state in {'corrupt', 'corrupted', 'poisoned'} or source_status in {'corrupt', 'corrupted', 'poisoned'}:
            decision_class = 'hard_deny'
            reason = 'economic_scope_corrupted_artifact'
            allowed = False
        elif current_key and incoming_key and current_key != incoming_key:
            declared = declared_old == current_key and declared_new == incoming_key
            if declared and declared_mode in {'', 'migrate-with-lineage', 'migrate_with_lineage', 'migration'}:
                decision_class = 'migrate-with-lineage'
                reason = 'economic_scope_migration_declared'
                allowed = True
            elif declared and review_state in {'quarantine', 'needs_review'}:
                decision_class = 'quarantine'
                reason = 'economic_scope_migration_quarantined'
                allowed = False
            else:
                decision_class = 'hard_deny'
                reason = 'economic_scope_migration_ambiguous'
                allowed = False
        elif profile_changed:
            if declared_old == current_key and declared_new == incoming_key and declared_mode in {'migrate-with-lineage', 'migrate_with_lineage', 'migration'}:
                decision_class = 'migrate-with-lineage'
                reason = 'economic_scope_profile_migration_declared'
                allowed = True
            else:
                decision_class = 'quarantine'
                reason = 'economic_scope_profile_drift_quarantine'
                allowed = False
        else:
            decision_class = 'allowed'
            reason = 'economic_scope_lineage_ok'
            allowed = True

        return EconomicScopeLineageVerdict(
            lineage_clear=allowed,
            old_scope_key=current_key,
            new_scope_key=incoming_key,
            migration_allowed=allowed,
            decision_class=decision_class,
            reason=reason,
            metadata={
                'owner': 'execution.economic_scope_lineage',
                'profile_changed': profile_changed,
                'declared_mode': declared_mode,
            },
        )


__all__ = [
    'CANON_ECONOMIC_SCOPE_LINEAGE',
    'EconomicScopeLineageVerdict',
    'EconomicScopeLineageGuard',
]
