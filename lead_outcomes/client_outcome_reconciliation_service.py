from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from lead_outcomes.client_outcome_commercial_state_store import ClientOutcomeCommercialStateService
from lead_outcomes.client_outcome_corrected_economics_store import ClientOutcomeCorrectedEconomicsService
from lead_outcomes.client_outcome_lifecycle_store import ClientOutcomeLifecyclePersistenceService


CANON_CLIENT_OUTCOME_RECONCILIATION_SERVICE = True


def _safe_dict(value: object) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _safe_float(value: object) -> float | None:
    if value in (None, ''):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _append_issue(issues: list[str], code: str) -> None:
    if code not in issues:
        issues.append(code)


def _has_stage(lifecycle_stages: Mapping[str, object], stage_name: str) -> bool:
    return str(stage_name).strip() in lifecycle_stages


def _reversal_expected_for_status(commercial_status: str) -> bool:
    return commercial_status in {'partial_reversed', 'reversed', 'closed'}


def _required_lifecycle_stage_names(*, commercial_status: str, has_billed_revenue: bool, has_corrected_economics: bool, has_dispute: bool, has_reversal: bool, has_refund_request: bool) -> tuple[str, ...]:
    required = ['selected_and_executed']
    if commercial_status in {'verified', 'billed', 'disputed', 'partial_reversed', 'reversed', 'closed'}:
        required.append('verified')
    if has_billed_revenue:
        required.append('billed')
    if has_dispute or commercial_status == 'disputed':
        required.append('dispute_opened')
    if has_reversal or _reversal_expected_for_status(commercial_status):
        required.append('reversed')
    if has_corrected_economics:
        required.append('corrected_economics')
    if has_refund_request:
        required.append('refund_requested')
    return tuple(required)


@dataclass(frozen=True, slots=True)
class ClientOutcomeReconciliationResult:
    found: bool
    order_id: str
    lead_id: str
    consistent: bool
    issues: tuple[str, ...]
    commercial_status: str
    economics_status: str
    reversal_amount: float | None
    corrected_revenue: dict[str, Any] | None
    commercial_state: dict[str, Any] | None
    corrected_economics: dict[str, Any] | None
    lifecycle: dict[str, Any] | None


@dataclass(frozen=True, slots=True)
class ClientOutcomeReconciliationService:
    commercial_state_service: ClientOutcomeCommercialStateService
    corrected_economics_service: ClientOutcomeCorrectedEconomicsService
    lifecycle_service: ClientOutcomeLifecyclePersistenceService | None = None

    def reconcile(self, *, order_id: str, lead_id: str) -> ClientOutcomeReconciliationResult:
        commercial_state = self.commercial_state_service.get_state(order_id=order_id, lead_id=lead_id)
        corrected_economics = self.corrected_economics_service.get_state(order_id=order_id, lead_id=lead_id)
        lifecycle = None if self.lifecycle_service is None else self.lifecycle_service.get_state(order_id=order_id, lead_id=lead_id)
        found = commercial_state is not None or corrected_economics is not None or lifecycle is not None
        if not found:
            return ClientOutcomeReconciliationResult(
                found=False,
                order_id=str(order_id or ''),
                lead_id=str(lead_id or ''),
                consistent=False,
                issues=(),
                commercial_status='',
                economics_status='',
                reversal_amount=None,
                corrected_revenue=None,
                commercial_state=None,
                corrected_economics=None,
                lifecycle=None,
            )

        issues: list[str] = []
        commercial_payload = _safe_dict(commercial_state)
        corrected_payload = _safe_dict(corrected_economics)
        lifecycle_payload = _safe_dict(lifecycle)
        lifecycle_stages = _safe_dict(lifecycle_payload.get('stages'))

        if not commercial_payload:
            _append_issue(issues, 'missing_commercial_state')
        if not corrected_payload:
            _append_issue(issues, 'missing_corrected_economics')

        commercial_status = str(commercial_payload.get('commercial_status') or '')
        economics_status = str(corrected_payload.get('economics_status') or '')

        commercial_reversal = _safe_dict(commercial_payload.get('reversal'))
        corrected_reversal = _safe_dict(corrected_payload.get('reversal'))
        commercial_has_reversal = bool(commercial_reversal)
        corrected_has_reversal = bool(corrected_reversal)
        has_any_reversal = commercial_has_reversal or corrected_has_reversal
        if commercial_has_reversal != corrected_has_reversal:
            _append_issue(issues, 'reversal_presence_mismatch')

        commercial_reversal_amount = _safe_float(commercial_reversal.get('amount')) if commercial_has_reversal else 0.0
        corrected_reversal_amount = _safe_float(corrected_reversal.get('amount')) if corrected_has_reversal else 0.0
        if commercial_reversal_amount != corrected_reversal_amount:
            _append_issue(issues, 'reversal_amount_mismatch')

        commercial_dispute = _safe_dict(commercial_payload.get('dispute'))
        has_dispute = bool(commercial_dispute)
        if commercial_status in {'disputed', 'partial_reversed', 'reversed', 'closed'} and not has_dispute:
            _append_issue(issues, 'missing_dispute_payload')

        commercial_corrected_revenue = _safe_dict(commercial_payload.get('revenue_after_reversal'))
        if not commercial_corrected_revenue:
            commercial_corrected_revenue = _safe_dict(commercial_payload.get('revenue_before_reversal'))
        corrected_revenue = _safe_dict(corrected_payload.get('corrected_revenue'))
        refund_preview = _safe_dict(corrected_payload.get('refund_preview'))
        refund_request = _safe_dict(corrected_payload.get('refund_request'))
        has_refund_preview = bool(refund_preview)
        has_refund_request = bool(refund_request)
        has_billed_revenue = bool(commercial_payload.get('revenue_before_reversal')) or bool(commercial_corrected_revenue)
        has_corrected_economics = bool(corrected_payload)
        if not commercial_corrected_revenue and corrected_revenue:
            _append_issue(issues, 'missing_commercial_corrected_revenue')
        if commercial_corrected_revenue and not corrected_revenue:
            _append_issue(issues, 'missing_corrected_revenue')

        compare_keys = ('billed_revenue', 'billable_clients', 'verified_clients', 'currency')
        for key in compare_keys:
            left = commercial_corrected_revenue.get(key)
            right = corrected_revenue.get(key)
            if key == 'billed_revenue':
                if _safe_float(left) != _safe_float(right):
                    _append_issue(issues, 'corrected_revenue_billed_revenue_mismatch')
            elif left != right:
                _append_issue(issues, f'corrected_revenue_{key}_mismatch')

        if commercial_has_reversal and economics_status and economics_status != 'corrected':
            _append_issue(issues, 'economics_status_not_corrected')
        if (not commercial_has_reversal) and economics_status and economics_status != 'uncorrected':
            _append_issue(issues, 'economics_status_unexpected')
        if _reversal_expected_for_status(commercial_status) and not has_any_reversal:
            _append_issue(issues, 'commercial_status_requires_reversal')
        if has_refund_preview and not has_any_reversal:
            _append_issue(issues, 'refund_preview_without_reversal')
        if has_refund_request and not has_refund_preview:
            _append_issue(issues, 'refund_request_without_preview')
        if has_refund_preview and not has_refund_request:
            _append_issue(issues, 'missing_refund_request')
        if has_refund_request:
            if _safe_float(refund_request.get('amount_minor')) != (_safe_float(commercial_reversal_amount) or 0.0) * 100.0:
                _append_issue(issues, 'refund_request_amount_minor_mismatch')
            if str(refund_request.get('currency') or '') != str((corrected_reversal or commercial_reversal).get('currency') or ''):
                _append_issue(issues, 'refund_request_currency_mismatch')

        if corrected_payload and not lifecycle_payload:
            _append_issue(issues, 'missing_lifecycle_state')
        for stage_name in _required_lifecycle_stage_names(
            commercial_status=commercial_status,
            has_billed_revenue=has_billed_revenue,
            has_corrected_economics=has_corrected_economics,
            has_dispute=has_dispute,
            has_reversal=has_any_reversal,
            has_refund_request=has_refund_request,
        ):
            if not _has_stage(lifecycle_stages, stage_name):
                _append_issue(issues, f'missing_lifecycle_{stage_name}_stage')

        if _has_stage(lifecycle_stages, 'reversed') and not has_any_reversal:
            _append_issue(issues, 'lifecycle_reversed_without_reversal_payload')
        if _has_stage(lifecycle_stages, 'dispute_opened') and not has_dispute:
            _append_issue(issues, 'lifecycle_dispute_without_dispute_payload')
        if _has_stage(lifecycle_stages, 'refund_requested') and not has_refund_request:
            _append_issue(issues, 'lifecycle_refund_requested_without_refund_request')

        return ClientOutcomeReconciliationResult(
            found=True,
            order_id=str((commercial_payload or corrected_payload or lifecycle_payload).get('order_id') or order_id),
            lead_id=str((commercial_payload or corrected_payload or lifecycle_payload).get('lead_id') or lead_id),
            consistent=not issues,
            issues=tuple(issues),
            commercial_status=commercial_status,
            economics_status=economics_status,
            reversal_amount=corrected_reversal_amount if corrected_has_reversal else commercial_reversal_amount,
            corrected_revenue=corrected_revenue or None,
            commercial_state=commercial_payload or None,
            corrected_economics=corrected_payload or None,
            lifecycle=lifecycle_payload or None,
        )
