from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from collections.abc import Mapping

CANON_ECONOMIC_BACKEND_AUTHORITY = True

DEFAULT_SEGMENT_QUORUM_POLICY = {
    'trace': 'strict',
    'metrics': 'soft',
    'roi': 'medium',
    'feedback': 'medium',
    'snapshots': 'strict',
}

DEFAULT_BACKEND_ROLE_POLICY = {
    'authoritative': 'source_of_truth',
    'primary': 'source_of_truth',
    'leader': 'source_of_truth',
    'replica': 'eligible_replica',
    'secondary': 'eligible_replica',
    'advisory': 'advisory_only',
    'readonly': 'advisory_only',
    'read_only': 'advisory_only',
    'quarantine': 'quarantine_only',
}

SEGMENT_MIN_SUPPORT_BY_POLICY = {
    'strict': 2,
    'medium': 1,
    'soft': 1,
}

ROLE_PRIORITY = {
    'source_of_truth': 4,
    'eligible_replica': 3,
    'advisory_only': 1,
    'quarantine_only': 0,
}


def _safe_dict(value: object) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _text(value: object) -> str:
    return str(value or '').strip()


def _score_for_policy(*, count: int, policy: str) -> int:
    base = max(0, int(count))
    if policy == 'strict':
        return base * 5
    if policy == 'medium':
        return base * 3
    if policy == 'soft':
        return base * 1
    return base * 2


@dataclass(frozen=True, slots=True)
class EconomicBackendAuthorityVerdict:
    authoritative_backend: str | None
    authoritative_policy: str = 'authoritative'
    lagging_backends: tuple[str, ...] = ()
    quarantined_backends: tuple[str, ...] = ()
    advisory_backends: tuple[str, ...] = ()
    stale_backends: tuple[str, ...] = ()
    segment_winners: dict[str, str] = field(default_factory=dict)
    backend_role_matrix: dict[str, str] = field(default_factory=dict)
    divergence_matrix: dict[str, str] = field(default_factory=dict)
    reason: str = 'economic_backend_authority_clear'
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            'authoritative_backend': self.authoritative_backend,
            'authoritative_policy': self.authoritative_policy,
            'lagging_backends': list(self.lagging_backends),
            'quarantined_backends': list(self.quarantined_backends),
            'advisory_backends': list(self.advisory_backends),
            'stale_backends': list(self.stale_backends),
            'segment_winners': dict(self.segment_winners),
            'backend_role_matrix': dict(self.backend_role_matrix),
            'divergence_matrix': dict(self.divergence_matrix),
            'reason': self.reason,
            'metadata': dict(self.metadata),
        }


class EconomicBackendAuthorityResolver:
    def build(
        self,
        *,
        backend_views: list[Mapping[str, Any]] | tuple[Mapping[str, Any], ...],
        segment_quorum_policy: Mapping[str, str] | None = None,
        backend_role_policy: Mapping[str, str] | None = None,
    ) -> EconomicBackendAuthorityVerdict:
        normalized = [_safe_dict(v) for v in backend_views]
        if not normalized:
            return EconomicBackendAuthorityVerdict(
                authoritative_backend=None,
                reason='economic_backend_authority_empty',
                metadata={'owner': 'execution.economic_backend_authority'},
            )

        policy = {**DEFAULT_SEGMENT_QUORUM_POLICY, **_safe_dict(segment_quorum_policy)}
        role_policy = {**DEFAULT_BACKEND_ROLE_POLICY, **_safe_dict(backend_role_policy)}
        score_rows: list[tuple[int, int, str]] = []
        quarantined: list[str] = []
        advisory: list[str] = []
        stale: list[str] = []
        segment_winners: dict[str, str] = {}
        segment_best: dict[str, tuple[int, int, str]] = {}
        role_matrix: dict[str, str] = {}
        divergence_matrix: dict[str, str] = {}
        segment_support_matrix: dict[str, dict[str, int]] = {}
        eligibility_matrix: dict[str, dict[str, Any]] = {}
        denied_segments_by_backend: dict[str, list[str]] = {}

        for view in normalized:
            name = _text(view.get('backend_name')) or 'unknown'
            status = _text(view.get('consistency_status') or view.get('status')).lower()
            declared_role = _text(view.get('backend_role')).lower() or 'replica'
            contract_role = _text(role_policy.get(declared_role) or role_policy.get('replica') or 'eligible_replica').lower()
            role_matrix[name] = contract_role

            scope_mismatch = bool(view.get('scope_mismatch')) or bool(view.get('profile_mismatch'))
            stale_branch = bool(view.get('stale_branch')) or status in {'stale', 'demoted'}
            corrupted = status in {'corrupt', 'corrupted', 'quarantined', 'invalid'} or bool(view.get('corrupted'))

            if corrupted or contract_role == 'quarantine_only':
                quarantined.append(name)
                divergence_matrix[name] = 'quarantine'
                eligibility_matrix[name] = {'contract_role': contract_role, 'eligible': False, 'denied_segments': ['all']}
                continue
            if stale_branch:
                stale.append(name)
                divergence_matrix[name] = 'stale_branch'
                eligibility_matrix[name] = {'contract_role': contract_role, 'eligible': False, 'denied_segments': ['all']}
                continue
            is_advisory = contract_role == 'advisory_only'
            if is_advisory:
                advisory.append(name)
                divergence_matrix[name] = 'advisory_only'

            total = 0
            segment_counts = {
                'snapshots': int(view.get('snapshot_count') or 0),
                'trace': int(view.get('trace_count') or 0),
                'feedback': int(view.get('feedback_count') or 0),
                'roi': int(view.get('roi_count') or 0),
                'metrics': int(view.get('metrics_count') or 0),
            }
            denied_segments: list[str] = []
            role_priority = ROLE_PRIORITY.get(contract_role, 0)
            for segment_name, count in segment_counts.items():
                policy_name = _text(policy.get(segment_name) or policy.get(segment_name.rstrip('s')) or 'medium').lower()
                minimum_support = SEGMENT_MIN_SUPPORT_BY_POLICY.get(policy_name, 1)
                segment_support_matrix.setdefault(segment_name, {})[name] = count
                if count < minimum_support:
                    denied_segments.append(segment_name)
                total += _score_for_policy(count=count, policy=policy_name)
                current = (count, role_priority, name)
                best = segment_best.get(segment_name)
                if best is None or current > best:
                    segment_best[segment_name] = current

            if scope_mismatch:
                total -= 1000
                divergence_matrix[name] = 'scope_mismatch'
            if is_advisory:
                total -= 10000
            if denied_segments:
                total -= 500 * len(denied_segments)
            denied_segments_by_backend[name] = denied_segments
            eligibility_matrix[name] = {
                'contract_role': contract_role,
                'eligible': not is_advisory and not scope_mismatch and not denied_segments,
                'denied_segments': list(denied_segments),
            }
            score_rows.append((role_priority, total, name))
            divergence_matrix.setdefault(name, 'eligible')

        if not score_rows:
            return EconomicBackendAuthorityVerdict(
                authoritative_backend=None,
                lagging_backends=(),
                quarantined_backends=tuple(sorted(dict.fromkeys(quarantined))),
                advisory_backends=tuple(sorted(dict.fromkeys(advisory))),
                stale_backends=tuple(sorted(dict.fromkeys(stale))),
                backend_role_matrix=role_matrix,
                divergence_matrix=divergence_matrix,
                reason='economic_backend_authority_all_quarantined',
                metadata={
                    'owner': 'execution.economic_backend_authority',
                    'segment_quorum_policy': dict(policy),
                    'backend_role_policy': dict(role_policy),
                    'segment_support_matrix': segment_support_matrix,
                    'eligibility_matrix': eligibility_matrix,
                },
            )

        score_rows.sort(reverse=True)
        # Winner selection is constrained by role priority and denied segments.
        authoritative = None
        authoritative_policy = 'authoritative'
        lagging_candidates: list[str] = []
        for role_priority, total, name in score_rows:
            eligibility = _safe_dict(eligibility_matrix.get(name))
            if authoritative is None and bool(eligibility.get('eligible')):
                authoritative = name
                if denied_segments_by_backend.get(name):
                    authoritative_policy = 'authoritative_with_segment_gaps'
                continue
            lagging_candidates.append(name)
        if authoritative is None:
            authoritative = score_rows[0][2]
            authoritative_policy = 'degraded_authoritative_fallback'
            divergence_matrix[authoritative] = 'degraded_fallback'
            lagging_candidates = [name for _, _, name in score_rows[1:]]

        lagging = tuple(lagging_candidates)
        for segment_name, (_, _, winner_name) in segment_best.items():
            segment_winners[segment_name] = winner_name

        reason = 'economic_backend_authority_resolved'
        if tuple(sorted(dict.fromkeys(quarantined))):
            reason = 'economic_backend_authority_resolved_with_quarantine'
        if tuple(sorted(dict.fromkeys(stale))):
            reason = 'economic_backend_authority_resolved_with_stale_handoff'
        if authoritative_policy != 'authoritative':
            reason = 'economic_backend_authority_resolved_degraded'

        return EconomicBackendAuthorityVerdict(
            authoritative_backend=authoritative,
            authoritative_policy=authoritative_policy,
            lagging_backends=lagging,
            quarantined_backends=tuple(sorted(dict.fromkeys(quarantined))),
            advisory_backends=tuple(sorted(dict.fromkeys(advisory))),
            stale_backends=tuple(sorted(dict.fromkeys(stale))),
            segment_winners=segment_winners,
            backend_role_matrix=role_matrix,
            divergence_matrix=divergence_matrix,
            reason=reason,
            metadata={
                'owner': 'execution.economic_backend_authority',
                'segment_quorum_policy': dict(policy),
                'backend_role_policy': dict(role_policy),
                'scored_backend_count': len(score_rows),
                'segment_support_matrix': segment_support_matrix,
                'eligibility_matrix': eligibility_matrix,
                'authoritative_contract': {
                    'winner': authoritative,
                    'winner_policy': authoritative_policy,
                    'winner_denied_segments': list(denied_segments_by_backend.get(authoritative, ())),
                    'quarantined_backends': tuple(sorted(dict.fromkeys(quarantined))),
                    'stale_backends': tuple(sorted(dict.fromkeys(stale))),
                },
            },
        )


__all__ = [
    'CANON_ECONOMIC_BACKEND_AUTHORITY',
    'DEFAULT_SEGMENT_QUORUM_POLICY',
    'DEFAULT_BACKEND_ROLE_POLICY',
    'SEGMENT_MIN_SUPPORT_BY_POLICY',
    'ROLE_PRIORITY',
    'EconomicBackendAuthorityVerdict',
    'EconomicBackendAuthorityResolver',
]
