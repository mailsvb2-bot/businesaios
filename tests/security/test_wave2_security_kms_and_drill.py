from __future__ import annotations

from pathlib import Path

from security.governance_owner_factory import build_security_governance_infrastructure
from security.kms_provider_sqlite import SQLiteKMSProvider


def test_sqlite_kms_provider_creates_and_reads_active_key(tmp_path: Path) -> None:
    provider = SQLiteKMSProvider(str(tmp_path / 'kms.sqlite3'))
    created = provider.create_key(key_id='approval-root', algorithm='HMAC-SHA256')
    active = provider.get_active_key(key_id='approval-root')

    assert created.key_id == 'approval-root'
    assert created.key_version == 1
    assert active.key_version == 1
    assert active.provider_name == 'sqlite-kms'


def test_security_governance_factory_exposes_drill_and_kms_registry(tmp_path: Path) -> None:
    infra = build_security_governance_infrastructure(base_dir=tmp_path, shared_secret='secret')

    drill = infra.drill_executor.run_token_quarantine_recovery_drill(
        actor='security-ops',
        token_fingerprint='fp-drill',
    )
    assert drill.success is True

    capabilities = infra.kms_registry.list_capabilities()
    provider_names = {item.provider_name for item in capabilities}
    assert 'inmemory-kms' in provider_names
    assert 'sqlite-kms' in provider_names
