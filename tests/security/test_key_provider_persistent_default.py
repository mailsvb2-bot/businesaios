from __future__ import annotations

from security.key_management_contract import KeyPurpose
from security.key_provider import FileKeyProvider, build_default_key_provider


def test_file_key_provider_roundtrip(tmp_path) -> None:
    path = tmp_path / 'keys.json'
    provider = FileKeyProvider(path=path)
    issued = provider.issue_key(key_id='webhook-v1', purpose=KeyPurpose.WEBHOOK_VERIFICATION)
    reloaded = FileKeyProvider(path=path)
    loaded = reloaded.get('webhook-v1')
    assert loaded.key_id == issued.key_id
    assert loaded.secret_bytes == issued.secret_bytes
    assert loaded.purpose is KeyPurpose.WEBHOOK_VERIFICATION


def test_build_default_key_provider_uses_file_backend(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv('BUSINESAIOS_DATA_DIR', str(tmp_path))
    monkeypatch.delenv('BUSINESAIOS_KEY_PROVIDER_BACKEND', raising=False)
    provider = build_default_key_provider()
    assert isinstance(provider, FileKeyProvider)
