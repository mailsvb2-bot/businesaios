from __future__ import annotations

from dataclasses import dataclass


CANON_SECURITY_APPROVAL_GATE = True


@dataclass(frozen=True)
class SecurityApprovalVerdict:
    allowed: bool
    requires_signed_approval: bool
    reason: str


class SecurityApprovalGate:
    _HIGH_RISK = {
        'key_rotate',
        'key_revoke',
        'secret_delete',
        'connector_secret_rebind',
        'audit_export_sign',
    }

    def evaluate(self, *, operation_kind: str) -> SecurityApprovalVerdict:
        operation = str(operation_kind or '').strip().lower()
        if not operation:
            raise ValueError('operation_kind is required')
        if operation in self._HIGH_RISK:
            return SecurityApprovalVerdict(True, True, f'high-risk security operation: {operation}')
        return SecurityApprovalVerdict(True, False, 'standard security operation')


__all__ = [
    'CANON_SECURITY_APPROVAL_GATE',
    'SecurityApprovalGate',
    'SecurityApprovalVerdict',
]
