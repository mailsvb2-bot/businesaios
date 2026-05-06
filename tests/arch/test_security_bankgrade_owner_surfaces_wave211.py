from __future__ import annotations

from pathlib import Path


_REQUIRED = {
    'security/kms_provider_backend.py',
    'security/kms_provider_local_hsm_adapter.py',
    'security/reencryption_job_store.py',
    'security/reencryption_progress_ledger.py',
    'security/reencryption_failure_policy.py',
    'security/reencryption_resume_service.py',
    'security/security_runtime_summary.py',
}


def test_security_bankgrade_owner_surfaces_exist() -> None:
    missing = [path for path in sorted(_REQUIRED) if not Path(path).exists()]
    assert not missing, f'missing security bank-grade owner surfaces: {missing}'


def test_security_runtime_summary_does_not_bypass_owner_layers() -> None:
    text = Path('security/security_runtime_summary.py').read_text(encoding='utf-8')
    assert 'sqlite3' not in text
    assert 'SecurityRuntimeSummaryService' in text
