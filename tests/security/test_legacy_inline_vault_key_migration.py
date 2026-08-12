from __future__ import annotations

import base64
import json
import os
from datetime import datetime, timezone
from pathlib import Path

import pytest

from security.key_management_contract import KeyMaterialRecord, KeyPurpose
from security.key_provider import FileKeyProvider, InMemoryKeyProvider
from security.secret_contract import SecretRef
from security.secret_vault import FileSecretVault, InMemorySecretVault, _serialize_secret_record
from tools import migrate_legacy_inline_vault_keys as migration


def _key(
    key_id: str,
    secret: bytes,
    *,
    purpose: KeyPurpose,
    tenant_id: str | None = None,
    connector_id: str | None = None,
) -> KeyMaterialRecord:
    moment = datetime(2026, 1, 1, tzinfo=timezone.utc)
    return KeyMaterialRecord(
        key_id=key_id,
        purpose=purpose,
        secret_bytes=secret,
        tenant_id=tenant_id,
        connector_id=connector_id,
        created_at=moment,
        activated_at=moment,
        metadata={"origin": "legacy-inline-vault-test"},
    )


def _legacy_key_payload(record: KeyMaterialRecord) -> dict[str, object]:
    return {
        "key_id": record.key_id,
        "purpose": record.purpose.value,
        "secret_b64": base64.b64encode(record.secret_bytes).decode("ascii"),
        "tenant_id": record.tenant_id,
        "connector_id": record.connector_id,
        "status": record.status.value,
        "created_at": record.created_at.isoformat(),
        "activated_at": record.activated_at.isoformat(),
        "expires_at": None,
        "metadata": dict(record.metadata),
    }


def _fixture(tmp_path: Path) -> tuple[Path, Path, Path, SecretRef, bytes]:
    security_dir = tmp_path / "security"
    security_dir.mkdir()
    provider_path = security_dir / "key_provider.json"
    vault_path = security_dir / "secret_vault.json"
    master_path = tmp_path / "key-provider-master.key"
    master_path.write_bytes(bytes(range(32)))

    provider_key = _key(
        "request-signing-v1",
        b"request-signing-key-material-32b",
        purpose=KeyPurpose.REQUEST_SIGNING,
    )
    inline_key = _key(
        "secret-tenant-connector-v1",
        b"legacy-inline-vault-key-material!",
        purpose=KeyPurpose.SECRET_ENCRYPTION,
        tenant_id="tenant",
        connector_id="connector",
    )
    provider_path.write_text(
        json.dumps({"records": [_legacy_key_payload(provider_key)]}),
        encoding="utf-8",
    )

    ref = SecretRef(tenant_id="tenant", secret_name="provider-token", connector_id="connector")
    legacy_provider = InMemoryKeyProvider(records=(inline_key,))
    legacy_vault = InMemorySecretVault(key_provider=legacy_provider)
    stored = legacy_vault.seed_plaintext(ref=ref, plaintext=b"existing-production-secret")
    vault_path.write_text(
        json.dumps(
            {
                "records": [_serialize_secret_record(stored)],
                "keys": [_legacy_key_payload(inline_key)],
            }
        ),
        encoding="utf-8",
    )
    return provider_path, vault_path, master_path, ref, bytes(stored.ciphertext)


def _set_master_env(monkeypatch, master_path: Path) -> None:
    monkeypatch.setenv(
        "BUSINESAIOS_KEY_PROVIDER_MASTER_KEY_B64",
        base64.b64encode(master_path.read_bytes()).decode("ascii"),
    )


def test_externalizes_inline_keys_wraps_merged_provider_and_preserves_ciphertext(monkeypatch, tmp_path) -> None:
    provider_path, vault_path, master_path, ref, original_ciphertext = _fixture(tmp_path)
    monkeypatch.setenv("APP_ENV", "prod")
    monkeypatch.delenv("BUSINESAIOS_KEY_PROVIDER_MASTER_KEY_B64", raising=False)
    original_provider = provider_path.read_bytes()
    original_vault = vault_path.read_bytes()

    plan = migration.build_migration_plan(
        secret_vault_path=vault_path,
        key_provider_path=provider_path,
        master_key_file=master_path,
    )
    assert plan.already_migrated is False
    assert plan.provider_format == "legacy"
    assert plan.provider_write_required is True
    assert len(plan.inline_keys) == 1
    assert len(plan.merged_keys) == 2

    result = migration.apply_migration(plan)

    assert result["applied"] is True
    assert result["validated_key_count"] == 2
    assert result["validated_secret_count"] == 1
    assert plan.provider_backup_path.read_bytes() == original_provider
    assert plan.vault_backup_path.read_bytes() == original_vault

    provider_payload = json.loads(provider_path.read_text(encoding="utf-8"))
    assert len(provider_payload["records"]) == 2
    assert all(item.get("key_envelope_version") == "BAIOS-KE2" for item in provider_payload["records"])
    assert all(item.get("wrapped_secret") for item in provider_payload["records"])
    assert all("secret_b64" not in item for item in provider_payload["records"])

    vault_payload = json.loads(vault_path.read_text(encoding="utf-8"))
    assert "keys" not in vault_payload
    assert vault_payload["key_storage"] == "external_key_provider"
    assert base64.b64decode(vault_payload["records"][0]["ciphertext_b64"]) == original_ciphertext

    _set_master_env(monkeypatch, master_path)
    provider = FileKeyProvider(path=provider_path)
    vault = FileSecretVault(root_dir=vault_path.parent, key_provider=provider)
    assert vault.get(ref) == b"existing-production-secret"

    second_plan = migration.build_migration_plan(
        secret_vault_path=vault_path,
        key_provider_path=provider_path,
        master_key_file=master_path,
    )
    assert second_plan.already_migrated is True
    second = migration.apply_migration(second_plan)
    assert second["applied"] is False
    assert second["validated_key_count"] == 2
    assert second["validated_secret_count"] == 1


def test_resumes_after_provider_replacement_before_vault_replacement(monkeypatch, tmp_path) -> None:
    provider_path, vault_path, master_path, ref, _ = _fixture(tmp_path)
    monkeypatch.setenv("APP_ENV", "prod")
    monkeypatch.delenv("BUSINESAIOS_KEY_PROVIDER_MASTER_KEY_B64", raising=False)
    plan = migration.build_migration_plan(
        secret_vault_path=vault_path,
        key_provider_path=provider_path,
        master_key_file=master_path,
    )

    real_replace = os.replace
    replacements = 0

    def interrupted_replace(source, destination):
        nonlocal replacements
        replacements += 1
        if replacements == 2:
            raise OSError("simulated crash between provider and vault replacement")
        return real_replace(source, destination)

    monkeypatch.setattr(migration.os, "replace", interrupted_replace)
    with pytest.raises(OSError, match="simulated crash"):
        migration.apply_migration(plan)
    monkeypatch.setattr(migration.os, "replace", real_replace)

    provider_payload = json.loads(provider_path.read_text(encoding="utf-8"))
    vault_payload = json.loads(vault_path.read_text(encoding="utf-8"))
    assert all(item.get("key_envelope_version") == "BAIOS-KE2" for item in provider_payload["records"])
    assert vault_payload.get("keys")

    retry = migration.build_migration_plan(
        secret_vault_path=vault_path,
        key_provider_path=provider_path,
        master_key_file=master_path,
    )
    assert retry.provider_format == "wrapped"
    assert retry.provider_write_required is False
    result = migration.apply_migration(retry)
    assert result["applied"] is True

    _set_master_env(monkeypatch, master_path)
    provider = FileKeyProvider(path=provider_path)
    vault = FileSecretVault(root_dir=vault_path.parent, key_provider=provider)
    assert vault.get(ref) == b"existing-production-secret"


def test_refuses_divergent_inline_key_collision(tmp_path) -> None:
    provider_path, vault_path, master_path, _, _ = _fixture(tmp_path)
    provider_payload = json.loads(provider_path.read_text(encoding="utf-8"))
    inline_payload = json.loads(vault_path.read_text(encoding="utf-8"))["keys"][0]
    conflicting = dict(inline_payload)
    conflicting["secret_b64"] = base64.b64encode(b"different-key-material-32-bytes!!").decode("ascii")
    provider_payload["records"].append(conflicting)
    provider_path.write_text(json.dumps(provider_payload), encoding="utf-8")

    with pytest.raises(RuntimeError, match="divergent key material"):
        migration.build_migration_plan(
            secret_vault_path=vault_path,
            key_provider_path=provider_path,
            master_key_file=master_path,
        )
