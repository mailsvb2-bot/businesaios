from __future__ import annotations

import base64
import json
from datetime import UTC, datetime

from security.key_management_contract import KeyPurpose
from security.key_provider import FileKeyProvider
from tools.migrate_legacy_inline_vault_keys import apply_migration, build_migration_plan, main


def _legacy_key_payload(secret: bytes) -> dict[str, object]:
    now = datetime.now(UTC).isoformat()
    return {
        "key_id": "secret-tenant-a-connector-a-v1",
        "purpose": KeyPurpose.SECRET_ENCRYPTION.value,
        "secret_b64": base64.b64encode(secret).decode("ascii"),
        "tenant_id": "tenant-a",
        "connector_id": "connector-a",
        "status": "active",
        "created_at": now,
        "activated_at": now,
        "expires_at": None,
        "metadata": {},
    }


def test_dry_run_is_read_only(monkeypatch, tmp_path, capsys) -> None:
    master = bytes(range(32))
    monkeypatch.setenv(
        "BUSINESAIOS_KEY_PROVIDER_MASTER_KEY_B64",
        base64.b64encode(master).decode("ascii"),
    )
    vault_path = tmp_path / "secret_vault.json"
    key_provider_path = tmp_path / "key_provider.json"
    payload = {"records": [], "keys": [_legacy_key_payload(b"legacy-secret-key")]}
    vault_path.write_text(json.dumps(payload), encoding="utf-8")

    assert main([
        "--vault-path",
        str(vault_path),
        "--key-provider-path",
        str(key_provider_path),
    ]) == 0

    output = json.loads(capsys.readouterr().out)
    assert output["applied"] is False
    assert json.loads(vault_path.read_text(encoding="utf-8")) == payload
    assert not key_provider_path.exists()
    assert not Path(str(vault_path) + ".legacy-inline-keys.bak").exists()


def test_apply_moves_keys_to_wrapped_provider_and_keeps_backup(monkeypatch, tmp_path) -> None:
    master = bytes(range(32))
    monkeypatch.setenv(
        "BUSINESAIOS_KEY_PROVIDER_MASTER_KEY_B64",
        base64.b64encode(master).decode("ascii"),
    )
    vault_path = tmp_path / "secret_vault.json"
    key_provider_path = tmp_path / "key_provider.json"
    secret = b"legacy-secret-key"
    payload = {
        "records": [{"ref": {"tenant_id": "tenant-a"}}],
        "keys": [_legacy_key_payload(secret)],
    }
    vault_path.write_text(json.dumps(payload), encoding="utf-8")
    plan = build_migration_plan(
        vault_path=vault_path,
        key_provider_path=key_provider_path,
    )

    result = apply_migration(plan)

    migrated = json.loads(vault_path.read_text(encoding="utf-8"))
    provider_text = key_provider_path.read_text(encoding="utf-8")
    provider = FileKeyProvider(path=key_provider_path)
    assert result["applied"] is True
    assert plan.backup_path.is_file()
    assert json.loads(plan.backup_path.read_text(encoding="utf-8")) == payload
    assert "keys" not in migrated
    assert migrated["key_storage"] == "external_key_provider"
    assert base64.b64encode(secret).decode("ascii") not in provider_text
    assert provider.get("secret-tenant-a-connector-a-v1").secret_bytes == secret
