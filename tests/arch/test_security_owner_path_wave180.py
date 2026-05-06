from __future__ import annotations

from pathlib import Path


def test_security_owner_path_exports_exist() -> None:
    for rel in (
        'security/security_policy_engine.py',
        'security/security_integration_adapter.py',
        'security/access_policy.py',
        'observability/immutable_event_store.py',
        'observability/security_audit_log.py',
    ):
        assert Path(rel).exists(), rel


def test_security_modules_do_not_import_decision_core() -> None:
    for rel in (
        'security/security_policy_engine.py',
        'security/security_integration_adapter.py',
        'security/access_policy.py',
        'security/fraud_detection_engine.py',
        'security/anomaly_detector.py',
    ):
        text = Path(rel).read_text(encoding='utf-8')
        assert 'DecisionCore' not in text
        assert 'optimize(' not in text
        assert 'decide(' not in text
