from __future__ import annotations

from pathlib import Path


def test_wave2_security_closure_owner_modules_exported() -> None:
    text = Path('security/__init__.py').read_text(encoding='utf-8')
    required = [
        'SQLiteSecurityOperatorWorkflowStore',
        'SQLiteSecurityIncidentDrillHistory',
        'SecurityAuditExportService',
        'SecurityIncidentRecoveryOrchestrator',
    ]
    missing = [item for item in required if item not in text]
    assert not missing, f'missing wave2 closure exports: {missing}'
