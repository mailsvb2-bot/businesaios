from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from runtime.platform.business_memory.compactor import BusinessMemoryCompactor
from runtime.platform.business_memory.policy import BusinessMemoryPolicy, DEFAULT_BUSINESS_MEMORY_POLICY
from runtime.platform.business_memory.projections import apply_step_feedback, merge_request_profile, to_runtime_context
from runtime.platform.business_memory.second_brain_boundary import sanitize_business_memory_payload
from runtime.platform.business_memory.store import FileBusinessMemoryStore

logger = logging.getLogger(__name__)
CANON_BUSINESS_MEMORY_SERVICE = True


@dataclass
class BusinessMemoryService:
    store: FileBusinessMemoryStore
    profile_store: Any | None = None
    state_registry: Any | None = None
    policy: BusinessMemoryPolicy = field(default_factory=lambda: DEFAULT_BUSINESS_MEMORY_POLICY)

    def __post_init__(self) -> None:
        self._compactor = BusinessMemoryCompactor(policy=self.policy)

    def _load_profile_overlay(self, *, business_id: str, tenant_id: str | None) -> dict[str, Any]:
        if self.profile_store is None:
            return {}
        try:
            try:
                profile = self.profile_store.get(str(business_id), tenant_id=str(tenant_id or ''))
            except TypeError:
                profile = self.profile_store.get(str(business_id))
        except Exception:
            logger.warning('business_memory: profile_store lookup failed for %s', business_id, exc_info=True)
            return {}
        return dict(getattr(profile, '__dict__', {}) or {})

    def _load_state_overlay(self, *, business_id: str, tenant_id: str | None) -> dict[str, Any]:
        if self.state_registry is None:
            return {}
        try:
            try:
                state_payload = self.state_registry.get(str(business_id), tenant_id=str(tenant_id or ''))
            except TypeError:
                state_payload = self.state_registry.get(str(business_id))
        except Exception:
            logger.warning('business_memory: state_registry lookup failed for %s', business_id, exc_info=True)
            return {}
        return dict(state_payload) if isinstance(state_payload, dict) and state_payload else {}

    def get(
        self,
        *,
        business_id: str,
        request_profile: dict[str, Any] | None = None,
        tenant_id: str | None = None,
    ) -> dict[str, Any]:
        record = self._compactor.compact(record=self.store.load(business_id=str(business_id), tenant_id=tenant_id))
        payload = record.to_dict()
        payload['profile'] = merge_request_profile(memory=record, request_profile=request_profile)
        payload['profile'] = {**self._load_profile_overlay(business_id=str(business_id), tenant_id=tenant_id), **dict(payload['profile'] or {})}
        state_overlay = self._load_state_overlay(business_id=str(business_id), tenant_id=tenant_id)
        if state_overlay:
            payload['business_state'] = state_overlay
        runtime_context = to_runtime_context(record)
        for key, value in runtime_context.items():
            if key in {'profile', 'business_id'}:
                continue
            payload[key] = value
        payload['tenant_id'] = str(tenant_id or payload.get('tenant_id') or '')
        return sanitize_business_memory_payload(payload)

    def update_after_step(
        self,
        *,
        business_id: str,
        feedback: dict[str, Any],
        action_type: str,
        request_meta: dict[str, Any] | None = None,
        tenant_id: str | None = None,
    ) -> dict[str, Any]:
        record = self.store.load(business_id=str(business_id), tenant_id=tenant_id)
        updated = apply_step_feedback(
            memory=record,
            feedback=dict(feedback or {}),
            action_type=str(action_type or ''),
            request_meta=dict(request_meta or {}),
        )
        compacted = self._compactor.compact(record=updated)
        self.store.save(compacted, tenant_id=tenant_id)
        payload = to_runtime_context(compacted)
        payload['tenant_id'] = str(tenant_id or '')
        return sanitize_business_memory_payload(payload)
