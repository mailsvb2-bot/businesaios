from __future__ import annotations

import base64
import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from security.key_management_contract import KeyMaterialRecord, KeyPurpose
from security.key_provider import FileKeyProvider, InMemoryKeyProvider
from security.secret_contract import SecretRef
from security.secret_vault import FileSecretVault
from tools import migrate_legacy_key_provider_envelopes as migration
from tools.migrate_legacy_key_provider_envelopes import apply_migration, build_migration_plan


def _record() -> KeyMaterialRecord:
    moment = datetime(2026, 1, 1, tzinfo=timezone.utc)
    return KeyMaterialRecord(
        key_id="secret-tenant-connector-v1",
        purpose=KeyPurpose.SECRET_ENCRYPTION,
        secret_bytes=b"legacy-provider-key-material-32b!",
        tenant_id="tenant",
        connector_id="connector",
        created_at=moment,
        activated_at=moment,
        metadata={"origin": "legacy-test"},
    )


def _legacy_payload(record: KeyMaterialRecord) -> dict[str, object]:
    return {
        "records": [
            {
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
        ]
    }


def _fixture(tmp_path: Path) -> tuple[Path, Path, Path, KeyMaterialRecord, SecretRef]:
    security_dir = tmp_path / "security"
    security_dir.mkdir()
    record = _record()
    ref = SecretRef(
        tenant_id="tenant",
        secret_name="provider-token",
        connector_id="connector",
    )
    legacy_provider = InMemoryKeyProvider(records=(record,))
    vault = FileSecretVault(root_dir=security_dir, key_provider=legacy_provider)
    vault.seed_plaintext(ref=ref, plaintext=b"existing-production-secret")

    provider_path = security_dir / "key_provider.json"
    provider_path.write_text(json.dumps(_legacy_payload(record)), encoding="utf-8")
    vault_path = security_dir / "secret_vault.json"
    master_path = tmp_path / "key-provider-master.key"
    master_path.write_bytes(bytes(range(32)))
    return provider_path, vault_path, master_path, record, ref


def test_migrates_legacy_secret_b64_and_proves_existing_vault(monkeypatch, tmp_path) -> None:
    provider_path, vault_path, master_path, record, ref = _fixture(tmp_path)
    monkeypatch.setenv("APP_ENV", "prod")
    monkeypatch.delenv("BUSINESAIOS_KEY_PROVIDER_MASTER_KEY_B64", raising=False)

    original = provider_path.read_bytes()
    plan = build_migration_plan(
        key_provider_path=provider_path,
        master_key_file=master_path,
        secret_vault_path=vault_path,
    )
    result = apply_migration(plan)

    assert result["applied"] is True
    assert result["validated_key_count"] == 1
    assert result["validated_secret_count"] == 1
    assert plan.backup_path.read_bytes() == original

    migrated = json.loads(provider_path.read_text(encoding="utf-8"))
    stored = migrated["records"][0]
    assert "secret_b64" not in stored
    assert stored["wrapped_secret"]
    assert stored["key_envelope_version"] == "BAIOS-KE2"

    monkeypatch.setenv(
        "BUSINESAIOS_KEY_PROVIDER_MASTER_KEY_B64",
        base64.b64encode(master_path.read_bytes()).decode("ascii"),
    )
    provider = FileKeyProvider(path=provider_path)
    assert provider.get(record.key_id).secret_bytes == record.secret_bytes
    migrated_vault = FileSecretVault(root_dir=vault_path.parent, key_provider=provider)
    assert migrated_vault.get(ref) == b"existing-production-secret"

    second_plan = build_migration_plan(
        key_provider_path=provider_path,
        master_key_file=master_path,
        secret_vault_path=vault_path,
    )
    assert second_plan.already_migrated is True
    second = apply_migration(second_plan)
    assert second["applied"] is False
    assert second["validated_key_count"] == 1
    assert second["validated_secret_count"] == 1


def test_retry_reuses_identical_backup_after_pre_replace_validation_failure(monkeypatch, tmp_path) -> None:
    provider_path, vault_path, master_path, _, _ = _fixture(tmp_path)
    monkeypatch.setenv("APP_ENV", "prod")
    monkeypatch.delenv("BUSINESAIOS_KEY_PROVIDER_MASTER_KEY_B64", raising=False)
    original = provider_path.read_bytes()
    plan = build_migration_plan(
        key_provider_path=provider_path,
        master_key_file=master_path,
        secret_vault_path=vault_path,
    )
    original_validate_vault = migration._validate_vault

    def fail_validation(*_args, **_kwargs):
        raise RuntimeError("simulated dependent vault validation failure")

    monkeypatch.setattr(migration, "_validate_vault", fail_validation)
    with pytest.raises(RuntimeError, match="simulated dependent vault validation failure"):
        migration.apply_migration(plan)

    assert provider_path.read_bytes() == original
    assert plan.backup_path.read_bytes() == original

    monkeypatch.setattr(migration, "_validate_vault", original_validate_vault)
    result = migration.apply_migration(plan)

    assert result["applied"] is True
    assert result["backup_created"] is False
    assert result["backup_available"] is True


def test_refuses_mixed_legacy_and_wrapped_record_formats(tmp_path) -> None:
    provider_path, vault_path, master_path, _, _ = _fixture(tmp_path)
    payload = json.loads(provider_path.read_text(encoding="utf-8"))
    payload["records"].append(
        {
            "key_id": "wrapped-key",
            "purpose": "request_signing",
            "wrapped_secret": "not-used-during-format-check",
            "key_envelope_version": "BAIOS-KE2",
        }
    )
    provider_path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(RuntimeError, match="mixes legacy, wrapped, or invalid"):
        build_migration_plan(
            key_provider_path=provider_path,
            master_key_file=master_path,
            secret_vault_path=vault_path,
        )


def test_refuses_invalid_master_key_size(tmp_path) -> None:
    provider_path, vault_path, master_path, _, _ = _fixture(tmp_path)
    master_path.write_bytes(b"too-short")

    with pytest.raises(RuntimeError, match="exactly 32 bytes"):
        build_migration_plan(
            key_provider_path=provider_path,
            master_key_file=master_path,
            secret_vault_path=vault_path,
        )
