from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

CANON_ECONOMIC_REPLAY_EPOCH_GUARD = True
DEFAULT_MAX_REPLAY_CHAIN_DEPTH = 64


def _safe_dict(value: object) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _safe_list(value: object) -> list[Any]:
    return list(value) if isinstance(value, (list, tuple)) else []


def _text(value: object) -> str:
    return str(value or '').strip()


@dataclass(frozen=True, slots=True)
class EconomicReplayEpochVerdict:
    overlapping_epoch_detected: bool
    current_epoch: str
    incoming_epoch: str
    accepted: bool
    reason: str
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            'overlapping_epoch_detected': bool(self.overlapping_epoch_detected),
            'current_epoch': self.current_epoch,
            'incoming_epoch': self.incoming_epoch,
            'accepted': bool(self.accepted),
            'reason': self.reason,
            'metadata': dict(self.metadata),
        }


class EconomicReplayEpochGuard:
    def validate(
        self,
        *,
        current_state: Mapping[str, Any] | None,
        incoming_payload: Mapping[str, Any] | None,
    ) -> EconomicReplayEpochVerdict:
        current = _safe_dict(current_state)
        incoming = _safe_dict(incoming_payload)
        current_meta = _safe_dict(current.get('meta'))
        incoming_meta = _safe_dict(incoming.get('metadata'))
        current_epoch = _text(current_meta.get('economic_replay_epoch'))
        incoming_epoch = _text(incoming_meta.get('replay_epoch'))
        current_resume_token = _text(current_meta.get('economic_resume_token'))
        incoming_resume_token = _text(incoming_meta.get('resume_token'))
        current_progress = _text(current_meta.get('economic_restore_status')).lower()
        incoming_progress = _text(incoming_meta.get('restore_status')).lower()
        current_schema_version = _text(current_meta.get('economic_bundle_schema_version') or current_meta.get('economic_schema_version'))
        incoming_schema_version = _text(incoming_meta.get('bundle_schema_version') or incoming_meta.get('schema_version'))
        current_anchor = _text(current_meta.get('economic_replay_anchor') or current_meta.get('replay_anchor'))
        incoming_anchor = _text(incoming_meta.get('replay_anchor'))
        incoming_parent_epoch = _text(incoming_meta.get('parent_replay_epoch'))
        incoming_chain_depth = int(incoming_meta.get('replay_chain_depth') or 0)
        max_depth = int(incoming_meta.get('max_replay_chain_depth') or DEFAULT_MAX_REPLAY_CHAIN_DEPTH)
        replay_history = [str(item) for item in _safe_list(incoming_meta.get('replay_history')) if _text(item)]
        replay_branch_count = int(incoming_meta.get('replay_branch_count') or 1)
        replay_gap_count = int(incoming_meta.get('replay_gap_count') or 0)
        replay_anchor_digest = _text(incoming_meta.get('replay_anchor_digest'))
        current_anchor_digest = _text(current_meta.get('economic_replay_anchor_digest') or current_meta.get('replay_anchor_digest'))

        if current_epoch and incoming_epoch and current_epoch != incoming_epoch:
            return EconomicReplayEpochVerdict(
                overlapping_epoch_detected=True,
                current_epoch=current_epoch,
                incoming_epoch=incoming_epoch,
                accepted=False,
                reason='economic_replay_epoch_overlap',
                metadata={'owner': 'execution.economic_replay_epoch_guard'},
            )
        if current_progress in {'started', 'in_progress', 'restoring'} and incoming_progress in {'started', 'in_progress', 'restoring'}:
            if current_resume_token and incoming_resume_token and current_resume_token != incoming_resume_token:
                return EconomicReplayEpochVerdict(
                    overlapping_epoch_detected=True,
                    current_epoch=current_epoch,
                    incoming_epoch=incoming_epoch,
                    accepted=False,
                    reason='economic_replay_partial_progress_conflict',
                    metadata={
                        'owner': 'execution.economic_replay_epoch_guard',
                        'current_resume_token': current_resume_token,
                        'incoming_resume_token': incoming_resume_token,
                    },
                )
            if current_schema_version and incoming_schema_version and current_schema_version != incoming_schema_version:
                return EconomicReplayEpochVerdict(
                    overlapping_epoch_detected=True,
                    current_epoch=current_epoch,
                    incoming_epoch=incoming_epoch,
                    accepted=False,
                    reason='economic_replay_cross_version_conflict',
                    metadata={
                        'owner': 'execution.economic_replay_epoch_guard',
                        'current_schema_version': current_schema_version,
                        'incoming_schema_version': incoming_schema_version,
                    },
                )

        if incoming_chain_depth > max_depth:
            return EconomicReplayEpochVerdict(
                overlapping_epoch_detected=False,
                current_epoch=current_epoch,
                incoming_epoch=incoming_epoch,
                accepted=False,
                reason='economic_replay_chain_depth_exceeded',
                metadata={
                    'owner': 'execution.economic_replay_epoch_guard',
                    'incoming_chain_depth': incoming_chain_depth,
                    'max_replay_chain_depth': max_depth,
                },
            )
        if incoming_chain_depth > 0 and not incoming_parent_epoch:
            return EconomicReplayEpochVerdict(
                overlapping_epoch_detected=False,
                current_epoch=current_epoch,
                incoming_epoch=incoming_epoch,
                accepted=False,
                reason='economic_replay_orphan_chain',
                metadata={'owner': 'execution.economic_replay_epoch_guard', 'incoming_chain_depth': incoming_chain_depth},
            )
        if incoming_chain_depth > 0 and not incoming_anchor:
            return EconomicReplayEpochVerdict(
                overlapping_epoch_detected=False,
                current_epoch=current_epoch,
                incoming_epoch=incoming_epoch,
                accepted=False,
                reason='economic_replay_anchor_missing',
                metadata={'owner': 'execution.economic_replay_epoch_guard', 'incoming_chain_depth': incoming_chain_depth},
            )
        if replay_history and len(replay_history) != len(set(replay_history)):
            return EconomicReplayEpochVerdict(
                overlapping_epoch_detected=False,
                current_epoch=current_epoch,
                incoming_epoch=incoming_epoch,
                accepted=False,
                reason='economic_replay_branching_detected',
                metadata={'owner': 'execution.economic_replay_epoch_guard', 'replay_history': replay_history},
            )
        if replay_branch_count > 1:
            return EconomicReplayEpochVerdict(
                overlapping_epoch_detected=False,
                current_epoch=current_epoch,
                incoming_epoch=incoming_epoch,
                accepted=False,
                reason='economic_replay_multi_branch_conflict',
                metadata={'owner': 'execution.economic_replay_epoch_guard', 'replay_branch_count': replay_branch_count},
            )
        if replay_history and incoming_chain_depth and len(replay_history) != incoming_chain_depth:
            return EconomicReplayEpochVerdict(
                overlapping_epoch_detected=False,
                current_epoch=current_epoch,
                incoming_epoch=incoming_epoch,
                accepted=False,
                reason='economic_replay_gap_detected',
                metadata={
                    'owner': 'execution.economic_replay_epoch_guard',
                    'replay_history_length': len(replay_history),
                    'incoming_chain_depth': incoming_chain_depth,
                },
            )
        if replay_gap_count > 0:
            return EconomicReplayEpochVerdict(
                overlapping_epoch_detected=False,
                current_epoch=current_epoch,
                incoming_epoch=incoming_epoch,
                accepted=False,
                reason='economic_replay_multi_gap_conflict',
                metadata={'owner': 'execution.economic_replay_epoch_guard', 'replay_gap_count': replay_gap_count},
            )
        if current_anchor and incoming_anchor and current_anchor != incoming_anchor:
            return EconomicReplayEpochVerdict(
                overlapping_epoch_detected=False,
                current_epoch=current_epoch,
                incoming_epoch=incoming_epoch,
                accepted=False,
                reason='economic_replay_anchor_mismatch',
                metadata={
                    'owner': 'execution.economic_replay_epoch_guard',
                    'current_anchor': current_anchor,
                    'incoming_anchor': incoming_anchor,
                },
            )
        if current_anchor_digest and replay_anchor_digest and current_anchor_digest != replay_anchor_digest:
            return EconomicReplayEpochVerdict(
                overlapping_epoch_detected=False,
                current_epoch=current_epoch,
                incoming_epoch=incoming_epoch,
                accepted=False,
                reason='economic_replay_anchor_digest_mismatch',
                metadata={
                    'owner': 'execution.economic_replay_epoch_guard',
                    'current_anchor_digest': current_anchor_digest,
                    'incoming_anchor_digest': replay_anchor_digest,
                },
            )

        return EconomicReplayEpochVerdict(
            overlapping_epoch_detected=False,
            current_epoch=current_epoch,
            incoming_epoch=incoming_epoch,
            accepted=True,
            reason='economic_replay_epoch_ok',
            metadata={
                'owner': 'execution.economic_replay_epoch_guard',
                'incoming_chain_depth': incoming_chain_depth,
                'max_replay_chain_depth': max_depth,
                'replay_anchor': incoming_anchor,
            },
        )


__all__ = [
    'CANON_ECONOMIC_REPLAY_EPOCH_GUARD',
    'DEFAULT_MAX_REPLAY_CHAIN_DEPTH',
    'EconomicReplayEpochVerdict',
    'EconomicReplayEpochGuard',
]
