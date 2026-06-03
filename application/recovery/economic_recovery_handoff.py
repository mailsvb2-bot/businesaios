from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from collections.abc import Mapping

CANON_ECONOMIC_RECOVERY_HANDOFF = True


def _safe_dict(value: object) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _text(value: object) -> str:
    return str(value or '').strip()


@dataclass(frozen=True, slots=True)
class EconomicRecoveryHandoff:
    run_id: str
    trace_key: str
    recovery_action: str
    recovery_reason: str
    economic_bundle_id: str
    restart_resume_consistent: bool
    duplicate_feedback_events: int
    duplicate_roi_events: int
    operator_required: bool
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            'run_id': self.run_id,
            'trace_key': self.trace_key,
            'recovery_action': self.recovery_action,
            'recovery_reason': self.recovery_reason,
            'economic_bundle_id': self.economic_bundle_id,
            'restart_resume_consistent': bool(self.restart_resume_consistent),
            'duplicate_feedback_events': int(self.duplicate_feedback_events),
            'duplicate_roi_events': int(self.duplicate_roi_events),
            'operator_required': bool(self.operator_required),
            'metadata': dict(self.metadata),
        }


class EconomicRecoveryHandoffBuilder:
    """Read-only adapter that attaches economic replay audit facts to recovery flow."""

    def build(
        self,
        *,
        run_id: str,
        recovery_summary: Mapping[str, Any] | None,
        audit_summary: Mapping[str, Any] | None,
        bundle_id: str,
    ) -> EconomicRecoveryHandoff | None:
        recovery = _safe_dict(recovery_summary)
        if not recovery:
            return None
        audit = _safe_dict(audit_summary)
        return EconomicRecoveryHandoff(
            run_id=_text(run_id),
            trace_key=_text(recovery.get('trace_key')),
            recovery_action=_text(recovery.get('action')),
            recovery_reason=_text(recovery.get('reason')),
            economic_bundle_id=_text(bundle_id),
            restart_resume_consistent=bool(audit.get('restart_resume_consistent', False)),
            duplicate_feedback_events=int(audit.get('duplicate_feedback_events') or 0),
            duplicate_roi_events=int(audit.get('duplicate_roi_events') or 0),
            operator_required=bool(recovery.get('operator_required', False)),
            metadata={
                'owner': 'execution.economic_recovery_handoff',
                'resume_action': _text(recovery.get('resume_action')),
                'resume_stage': _text(recovery.get('resume_stage')),
            },
        )


__all__ = [
    'CANON_ECONOMIC_RECOVERY_HANDOFF',
    'EconomicRecoveryHandoff',
    'EconomicRecoveryHandoffBuilder',
]
