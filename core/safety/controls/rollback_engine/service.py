from __future__ import annotations

import hashlib

from ..action_context import SafetyActionContext
from ..action_identity import canonical_action_id
from ..rollback_verifier import RollbackVerificationError, RollbackVerifier
from .models import RollbackExecutionState, RollbackPlan, RollbackReceipt, RollbackReconciliationState
from .registry import RollbackRegistry
from .store import RollbackPlanStore


class RollbackPlanner:
    def __init__(
        self,
        registry: RollbackRegistry,
        store: RollbackPlanStore | None = None,
        verifier: RollbackVerifier | None = None,
    ):
        self._registry = registry
        self._store = store
        self._verifier = verifier or RollbackVerifier()

    def build(self, ctx: SafetyActionContext) -> RollbackPlan:
        plan = self._registry.plan_for(ctx)
        action_id = canonical_action_id(action=ctx.action, tenant_id=ctx.tenant_id, payload=ctx.payload)
        confirmation_token = hashlib.sha256(f"{ctx.tenant_id}:{action_id}:{ctx.action}".encode()).hexdigest()
        enriched = RollbackPlan(
            source_action=plan.source_action,
            steps=plan.steps,
            execution_state=RollbackExecutionState.PLANNED,
            confirmation_token=confirmation_token,
        )
        if self._store is not None:
            self._store.put(tenant_id=ctx.tenant_id, action_id=action_id, plan=enriched)
        return enriched

    def get_persisted(self, *, tenant_id: str, action_id: str) -> RollbackPlan | None:
        if self._store is None:
            return None
        return self._store.get(tenant_id=tenant_id, action_id=action_id)

    def confirm_execution(self, *, tenant_id: str, action_id: str, confirmation_token: str) -> RollbackPlan | None:
        if self._store is None:
            return None
        plan = self._store.get(tenant_id=tenant_id, action_id=action_id)
        if plan is None:
            return None
        if str(plan.confirmation_token or '') != str(confirmation_token or '').strip():
            raise ValueError('invalid rollback confirmation token')
        return self._store.update_state(tenant_id=tenant_id, action_id=action_id, state=RollbackExecutionState.CONFIRMED)

    def mark_executing(self, *, tenant_id: str, action_id: str) -> RollbackPlan | None:
        if self._store is None:
            return None
        return self._store.update_state(tenant_id=tenant_id, action_id=action_id, state=RollbackExecutionState.EXECUTING)

    def mark_executed(self, *, tenant_id: str, action_id: str) -> RollbackPlan | None:
        if self._store is None:
            return None
        return self._store.update_state(tenant_id=tenant_id, action_id=action_id, state=RollbackExecutionState.EXECUTED)

    def mark_failed(self, *, tenant_id: str, action_id: str) -> RollbackPlan | None:
        if self._store is None:
            return None
        return self._store.update_state(tenant_id=tenant_id, action_id=action_id, state=RollbackExecutionState.FAILED)

    def append_receipt(
        self,
        *,
        tenant_id: str,
        action_id: str,
        step_index: int,
        action: str,
        status: str,
        details: dict[str, object] | None = None,
    ) -> RollbackPlan | None:
        if self._store is None:
            return None
        return self._store.append_receipt(
            tenant_id=tenant_id,
            action_id=action_id,
            receipt=RollbackReceipt(
                step_index=int(step_index),
                action=str(action),
                status=str(status),
                details=dict(details or {}),
            ),
        )

    def reconcile(
        self,
        *,
        tenant_id: str,
        action_id: str,
        expected_state: dict[str, object],
        observed_state: dict[str, object],
    ) -> RollbackPlan | None:
        if self._store is None:
            return None
        try:
            self._verifier.verify(expected_state=expected_state, observed_state=observed_state)
            return self._store.update_reconciliation(
                tenant_id=tenant_id,
                action_id=action_id,
                state=RollbackReconciliationState.VERIFIED,
                error='',
            )
        except RollbackVerificationError as exc:
            return self._store.update_reconciliation(
                tenant_id=tenant_id,
                action_id=action_id,
                state=RollbackReconciliationState.DRIFTED,
                error=str(exc),
            )
