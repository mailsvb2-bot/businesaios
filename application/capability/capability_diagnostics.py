from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from application.capability.capability_fallback_contract import CapabilityFallbackDecision
from application.capability.capability_matrix import CapabilityRecord
from config.risk_evaluation_policy import DEFAULT_CAPABILITY_DIAGNOSTICS_POLICY

CANON_CAPABILITY_DIAGNOSTICS = True


def _text(value: object) -> str:
    return str(value or "").strip()


def _safe_dict(value: object) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


@dataclass(frozen=True)
class CapabilityDiagnosticSignal:
    code: str
    severity: str
    summary: str
    operator_actionable: bool = False
    metadata: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        payload = {
            'code': self.code,
            'severity': self.severity,
            'summary': self.summary,
            'operator_actionable': self.operator_actionable,
        }
        if self.metadata:
            payload['metadata'] = dict(self.metadata)
        return payload


@dataclass(frozen=True)
class CapabilityDiagnosticsReport:
    status: str
    headline: str
    operator_action: str
    signals: tuple[CapabilityDiagnosticSignal, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            'status': self.status,
            'headline': self.headline,
            'operator_action': self.operator_action,
            'signals': [signal.to_dict() for signal in self.signals],
        }


class CapabilityDiagnosticsBuilder:
    """
    Read-only operator-facing diagnostics builder.

    Important:
    - no goal selection
    - no decomposition
    - no second planner path
    - only summarizes capability preflight state for observability/handoff
    """

    def build(
        self,
        *,
        record: CapabilityRecord,
        allowed: bool,
        reason: str,
        routing_explanation: Mapping[str, Any] | None = None,
        execution_verdict: Mapping[str, Any] | None = None,
        fallback: CapabilityFallbackDecision | None = None,
        policy_verdict: Mapping[str, Any] | None = None,
    ) -> CapabilityDiagnosticsReport:
        runtime = record.runtime
        descriptor = record.descriptor
        signals: list[CapabilityDiagnosticSignal] = []

        if not allowed:
            signals.append(
                CapabilityDiagnosticSignal(
                    code='capability_blocked',
                    severity='critical',
                    summary=_text(reason) or 'capability blocked',
                    operator_actionable=True,
                    metadata={'action_type': record.action_type, 'capability_key': record.capability_key},
                )
            )

        if runtime.staleness_state == 'stale':
            signals.append(
                CapabilityDiagnosticSignal(
                    code='stale_evidence',
                    severity='high',
                    summary='Capability evidence is stale.',
                    operator_actionable=True,
                    metadata={'last_observed_at': runtime.last_observed_at or runtime.updated_at},
                )
            )
        elif runtime.staleness_state == 'cooling':
            signals.append(
                CapabilityDiagnosticSignal(
                    code='cooling_evidence',
                    severity='medium',
                    summary='Capability evidence is cooling and should be watched.',
                    operator_actionable=False,
                )
            )

        if runtime.evidence_state in {'unknown', 'insufficient'}:
            signals.append(
                CapabilityDiagnosticSignal(
                    code='insufficient_evidence',
                    severity='high' if runtime.evidence_state == 'unknown' else 'medium',
                    summary='Capability lacks sufficient trustworthy evidence.',
                    operator_actionable=True,
                    metadata={
                        'evidence_state': runtime.evidence_state,
                        'recommended_autonomy_tier': runtime.recommended_autonomy_tier,
                    },
                )
            )

        if runtime.confidence_score < DEFAULT_CAPABILITY_DIAGNOSTICS_POLICY.low_confidence_threshold:
            signals.append(
                CapabilityDiagnosticSignal(
                    code='low_confidence',
                    severity='medium',
                    summary='Capability confidence is low.',
                    operator_actionable=False,
                    metadata={'confidence_score': runtime.confidence_score},
                )
            )

        if not runtime.enabled:
            signals.append(
                CapabilityDiagnosticSignal(
                    code='runtime_disabled',
                    severity='critical',
                    summary='Runtime capability is disabled.',
                    operator_actionable=True,
                )
            )

        verdict = _safe_dict(execution_verdict)

        policy = _safe_dict(policy_verdict)
        if policy and policy.get('allowed') is False:
            signals.append(
                CapabilityDiagnosticSignal(
                    code='tenant_policy_blocked',
                    severity='high',
                    summary='Tenant or business capability policy denied this action.',
                    operator_actionable=True,
                    metadata={'reason': _text(policy.get('reason')), 'policy_scope': _text(policy.get('policy_scope'))},
                )
            )
        elif policy and policy.get('recommended_autonomy_tier') and _text(policy.get('recommended_autonomy_tier')) != _text(verdict.get('autonomy_tier')):
            signals.append(
                CapabilityDiagnosticSignal(
                    code='tenant_policy_tier_hint',
                    severity='medium',
                    summary='Tenant policy recommends a lower autonomy tier.',
                    operator_actionable=False,
                    metadata={'recommended_autonomy_tier': _text(policy.get('recommended_autonomy_tier'))},
                )
            )
        if verdict.get('approval_required'):
            signals.append(
                CapabilityDiagnosticSignal(
                    code='approval_required',
                    severity='medium',
                    summary='Human approval is required before execution.',
                    operator_actionable=True,
                )
            )
        if verdict.get('budget_allowed') is False:
            signals.append(
                CapabilityDiagnosticSignal(
                    code='budget_blocked',
                    severity='high',
                    summary='Execution budget denied this action.',
                    operator_actionable=True,
                    metadata={'reason': _text(verdict.get('reason'))},
                )
            )
        if verdict.get('blast_radius_allowed') is False:
            signals.append(
                CapabilityDiagnosticSignal(
                    code='blast_radius_blocked',
                    severity='high',
                    summary='Blast radius guard denied this action.',
                    operator_actionable=True,
                    metadata={'reason': _text(verdict.get('reason'))},
                )
            )

        if fallback is not None:
            signals.append(
                CapabilityDiagnosticSignal(
                    code='fallback_selected',
                    severity='high' if fallback.operator_handoff_required else 'medium',
                    summary=f'Fallback selected: {fallback.kind}.',
                    operator_actionable=bool(fallback.operator_handoff_required),
                    metadata=fallback.to_dict(),
                )
            )

        routing = _safe_dict(routing_explanation)
        routing_reason = _text(_safe_dict(routing.get('factors')).get('reason') or routing.get('reason'))
        if routing_reason and routing_reason not in {reason, 'capability_ok'}:
            signals.append(
                CapabilityDiagnosticSignal(
                    code='routing_reason',
                    severity='medium',
                    summary=f'Routing noted: {routing_reason}.',
                    operator_actionable=False,
                )
            )

        if not descriptor.prod_ready:
            signals.append(
                CapabilityDiagnosticSignal(
                    code='non_prod_ready',
                    severity='medium',
                    summary='Capability is not marked production ready.',
                    operator_actionable=False,
                )
            )

        if not signals:
            signals.append(
                CapabilityDiagnosticSignal(
                    code='capability_ok',
                    severity='info',
                    summary='Capability preflight is healthy.',
                    operator_actionable=False,
                )
            )

        if any(signal.operator_actionable for signal in signals):
            operator_action = 'review_and_handoff'
        elif any(signal.severity in {'high', 'critical'} for signal in signals):
            operator_action = 'monitor'
        else:
            operator_action = 'none'

        if not allowed:
            status = 'blocked'
            headline = f'Capability blocked for {record.action_type}.'
        elif fallback is not None:
            status = 'fallback'
            headline = f'Capability fallback selected for {record.action_type}.'
        elif any(signal.code in {'stale_evidence', 'insufficient_evidence', 'low_confidence'} for signal in signals):
            status = 'watch'
            headline = f'Capability requires attention for {record.action_type}.'
        else:
            status = 'ok'
            headline = f'Capability healthy for {record.action_type}.'

        return CapabilityDiagnosticsReport(
            status=status,
            headline=headline,
            operator_action=operator_action,
            signals=tuple(signals),
        )


__all__ = [
    'CANON_CAPABILITY_DIAGNOSTICS',
    'CapabilityDiagnosticSignal',
    'CapabilityDiagnosticsReport',
    'CapabilityDiagnosticsBuilder',
]
