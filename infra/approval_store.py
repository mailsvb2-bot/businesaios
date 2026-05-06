from __future__ import annotations

from dataclasses import dataclass, field

from governance.approval_store import InMemoryApprovalStore as CanonicalApprovalStore
from governance.approval_contract import ApprovalRequest as CanonicalApprovalRequest
from infra.approval_request import ApprovalRequest


CANON_INFRA_APPROVAL_STORE_ADAPTER = True


def _tenant_id_from(request: ApprovalRequest) -> str:
    payload = dict(request.payload or {})
    tenant_id = str(payload.get('tenant_id') or 'legacy').strip().lower()
    return tenant_id or 'legacy'


@dataclass
class InMemoryApprovalStore:
    """Legacy adapter over the canonical governance approval store.

    Keeps the legacy ``put/get/has/approve_step`` API so old infra paths continue
    to run, while canonical approval ownership stays in ``governance``.
    """

    _store: CanonicalApprovalStore = field(default_factory=CanonicalApprovalStore)
    _legacy_requests: dict[str, ApprovalRequest] = field(default_factory=dict)
    _approved_steps: dict[str, set[str]] = field(default_factory=dict)

    def put(self, request: ApprovalRequest) -> None:
        self._legacy_requests[request.request_id] = request
        self._approved_steps.setdefault(request.request_id, set())
        canonical_request = CanonicalApprovalRequest(
            approval_id=request.request_id,
            tenant_id=_tenant_id_from(request),
            subject_type=str(request.approval_type or 'legacy_approval').strip() or 'legacy_approval',
            subject_id=str(request.target_name or request.request_id).strip() or request.request_id,
            requested_by=str(request.actor or 'legacy').strip() or 'legacy',
            reason=f"legacy approval for {request.approval_type or 'unknown'}",
            metadata={
                'legacy_payload': dict(request.payload or {}),
                'legacy_required_steps': list(request.required_steps),
                'legacy_target_name': request.target_name,
            },
        )
        if self._store.get(request.request_id) is None:
            self._store.create(canonical_request)

    def get(self, request_id: str) -> ApprovalRequest:
        return self._legacy_requests[request_id]

    def has(self, request_id: str) -> bool:
        return request_id in self._legacy_requests

    def approve_step(self, request_id: str, step_name: str) -> None:
        if request_id not in self._legacy_requests:
            raise KeyError(request_id)
        self._approved_steps.setdefault(request_id, set()).add(step_name)

    def approved_steps(self, request_id: str) -> tuple[str, ...]:
        return tuple(sorted(self._approved_steps.get(request_id, set())))

    def list_requests(self) -> tuple[ApprovalRequest, ...]:
        return tuple(self._legacy_requests.values())
