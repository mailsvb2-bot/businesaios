from __future__ import annotations

import security


def test_wave2_security_namespace_exports() -> None:
    assert hasattr(security, 'RequestSignatureVerifier')
    assert hasattr(security, 'SQLiteSecurityAuditChain')
    assert hasattr(security, 'TenantSecretScope')
    assert hasattr(security, 'TenantSecretAccessPolicy')
    assert hasattr(security, 'SignedOperatorApprovalStore')
    assert hasattr(security, 'SecurityApprovalGate')
    assert hasattr(security, 'ReencryptionOrchestrator')
