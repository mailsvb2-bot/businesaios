from __future__ import annotations

from dataclasses import dataclass, field
from hashlib import sha256
import json
from typing import Any, Mapping

CANON_ECONOMIC_SPLIT_BRAIN_GUARD = True


def _safe_dict(value: object) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _text(value: object) -> str:
    return str(value or '').strip()


def _stable_digest(payload: Mapping[str, Any]) -> str:
    raw = json.dumps(dict(payload), ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return sha256(raw).hexdigest()


@dataclass(frozen=True, slots=True)
class EconomicSplitBrainVerdict:
    split_brain_detected: bool
    authoritative_node_id: str | None
    stale_node_ids: tuple[str, ...] = ()
    quarantined_node_ids: tuple[str, ...] = ()
    stale_node_demotions: dict[str, str] = field(default_factory=dict)
    winner_confirmation_marker: str = ''
    replay_refusal_markers: dict[str, str] = field(default_factory=dict)
    handoff_markers: dict[str, str] = field(default_factory=dict)
    stale_branch_digests: dict[str, str] = field(default_factory=dict)
    authoritative_lineage_digest: str = ''
    stale_lineage_rejections: dict[str, str] = field(default_factory=dict)
    epoch_monotonicity_ok: bool = True
    reason: str = 'economic_split_brain_clear'
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            'split_brain_detected': bool(self.split_brain_detected),
            'authoritative_node_id': self.authoritative_node_id,
            'stale_node_ids': list(self.stale_node_ids),
            'quarantined_node_ids': list(self.quarantined_node_ids),
            'stale_node_demotions': dict(self.stale_node_demotions),
            'winner_confirmation_marker': self.winner_confirmation_marker,
            'replay_refusal_markers': dict(self.replay_refusal_markers),
            'handoff_markers': dict(self.handoff_markers),
            'stale_branch_digests': dict(self.stale_branch_digests),
            'authoritative_lineage_digest': self.authoritative_lineage_digest,
            'stale_lineage_rejections': dict(self.stale_lineage_rejections),
            'epoch_monotonicity_ok': bool(self.epoch_monotonicity_ok),
            'reason': self.reason,
            'metadata': dict(self.metadata),
        }


class EconomicSplitBrainGuard:
    def build(
        self,
        *,
        node_views: list[Mapping[str, Any]] | tuple[Mapping[str, Any], ...],
    ) -> EconomicSplitBrainVerdict:
        normalized = [_safe_dict(v) for v in node_views]
        active = [v for v in normalized if bool(v.get('active', True))]
        if len(active) <= 1:
            winner = _text(active[0].get('node_id')) if active else None
            winner_epoch = int(active[0].get('leader_epoch') or active[0].get('authority_epoch') or 0) if active else 0
            winner_digest = _text(active[0].get('store_digest')) if active else ''
            lineage_digest = _stable_digest({
                'winner_id': winner or '',
                'winner_epoch': winner_epoch,
                'winner_digest': winner_digest,
                'parent_lineage_digest': _text(active[0].get('parent_lineage_digest')) if active else '',
            }) if active else ''
            return EconomicSplitBrainVerdict(
                split_brain_detected=False,
                authoritative_node_id=winner,
                winner_confirmation_marker=f'economic-winner::{winner}' if winner else '',
                handoff_markers={winner: f'economic-handoff-winner::{winner}'} if winner else {},
                authoritative_lineage_digest=lineage_digest,
                reason='economic_split_brain_clear',
                metadata={
                    'owner': 'execution.economic_split_brain_guard',
                    'handoff_contract_version': 'v4',
                    'lineage_sealed': bool(lineage_digest),
                    'authority_epoch_monotonic': True,
                },
            )

        has_authority_markers = any(
            int(row.get('leader_epoch') or row.get('authority_epoch') or 0) > 0
            or bool(_text(row.get('fencing_token')))
            or bool(_text(row.get('store_digest')))
            for row in active
        )
        if not has_authority_markers:
            winner = _text(active[0].get('node_id')) if active else None
            return EconomicSplitBrainVerdict(
                split_brain_detected=False,
                authoritative_node_id=winner,
                reason='economic_split_brain_clear',
                metadata={'owner': 'execution.economic_split_brain_guard', 'authority_epoch_monotonic': True, 'handoff_contract_version': 'v4', 'lineage_sealed': False},
            )

        ranked = sorted(
            active,
            key=lambda row: (
                int(row.get('leader_epoch') or row.get('authority_epoch') or 0),
                _text(row.get('fencing_token')),
                _text(row.get('node_id')),
            ),
            reverse=True,
        )
        winner = ranked[0]
        winner_id = _text(winner.get('node_id')) or None
        winner_digest = _text(winner.get('store_digest'))
        winner_epoch = int(winner.get('leader_epoch') or winner.get('authority_epoch') or 0)
        stale_ids = tuple(_text(row.get('node_id')) for row in ranked[1:] if _text(row.get('node_id')))
        digests = {_text(row.get('store_digest')) for row in ranked if _text(row.get('store_digest'))}
        split = len(digests) > 1 or len(ranked) > 1
        stale_demotions = {node_id: f'economic-stale-demotion::{node_id}@epoch<{winner_epoch}' for node_id in stale_ids}
        replay_refusals = {
            node_id: f'economic-replay-refusal::{node_id}->{winner_id}@digest={winner_digest or "unknown"}'
            for node_id in stale_ids
        }
        handoff_markers = {node_id: f'economic-handoff-stale::{node_id}->{winner_id}@epoch={winner_epoch}' for node_id in stale_ids if winner_id}
        if winner_id:
            handoff_markers[winner_id] = f'economic-handoff-winner::{winner_id}@epoch={winner_epoch}'
        confirmation = f'economic-winner::{winner_id}@epoch={winner_epoch}' if winner_id else ''
        stale_branch_digests = {
            _text(row.get('node_id')): _text(row.get('store_digest'))
            for row in ranked[1:]
            if _text(row.get('node_id')) and _text(row.get('store_digest'))
        }
        authoritative_lineage_digest = _stable_digest({
            'winner_id': winner_id or '',
            'winner_epoch': winner_epoch,
            'winner_digest': winner_digest,
            'parent_lineage_digest': _text(winner.get('parent_lineage_digest')),
        }) if winner_id else ''
        stale_lineage_rejections = {
            node_id: f'economic-stale-lineage-reject::{node_id}->{winner_id}@lineage={authoritative_lineage_digest or "missing"}'
            for node_id in stale_ids
        }
        monotonicity_violations = [
            _text(row.get('node_id'))
            for row in ranked[1:]
            if int(row.get('leader_epoch') or row.get('authority_epoch') or 0) >= winner_epoch
        ]
        epoch_monotonicity_ok = not monotonicity_violations

        return EconomicSplitBrainVerdict(
            split_brain_detected=split,
            authoritative_node_id=winner_id,
            stale_node_ids=stale_ids,
            quarantined_node_ids=stale_ids if split else (),
            stale_node_demotions=stale_demotions,
            winner_confirmation_marker=confirmation,
            replay_refusal_markers=replay_refusals,
            handoff_markers=handoff_markers,
            stale_branch_digests=stale_branch_digests,
            authoritative_lineage_digest=authoritative_lineage_digest,
            stale_lineage_rejections=stale_lineage_rejections,
            epoch_monotonicity_ok=epoch_monotonicity_ok,
            reason='economic_split_brain_detected' if split else 'economic_split_brain_clear',
            metadata={
                'owner': 'execution.economic_split_brain_guard',
                'active_node_count': len(ranked),
                'distinct_store_digest_count': len(digests),
                'winner_digest': winner_digest,
                'winner_epoch': winner_epoch,
                'handoff_contract_version': 'v4',
                'lineage_sealed': bool(authoritative_lineage_digest),
                'authority_epoch_monotonic': epoch_monotonicity_ok,
                'epoch_monotonicity_violations': monotonicity_violations,
                'stale_replay_handoff': {
                    'winner_id': winner_id,
                    'winner_epoch': winner_epoch,
                    'stale_nodes': list(stale_ids),
                    'authoritative_lineage_digest': authoritative_lineage_digest,
                },
            },
        )


__all__ = [
    'CANON_ECONOMIC_SPLIT_BRAIN_GUARD',
    'EconomicSplitBrainVerdict',
    'EconomicSplitBrainGuard',
]
