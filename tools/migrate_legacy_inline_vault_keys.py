from __future__ import annotations

import argparse
import base64
import filecmp
import json
import os
import shutil
import tempfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Mapping, Sequence

from security.encryption_policy import EncryptionPolicy
from security.key_management_contract import KeyMaterialRecord, KeyPurpose, KeyStatus
from security.key_provider import FileKeyProvider, InMemoryKeyProvider, _serialize_record
from security.secret_vault import InMemorySecretVault, _deserialize_secret_record, decrypt_secret_payload
from tools.migrate_legacy_key_provider_envelopes import _master_key_environment, _read_master_key


@dataclass(frozen=True)
class LegacyInlineVaultKeyMigrationPlan:
    secret_vault_path: Path
    key_provider_path: Path
    master_key_file: Path
    vault_backup_path: Path
    provider_backup_path: Path
    vault_payload: Mapping[str, object]
    provider_payload: Mapping[str, object]
    vault_records: tuple[Mapping[str, object], ...]
    inline_keys: tuple[KeyMaterialRecord, ...]
    provider_keys: tuple[KeyMaterialRecord, ...]
    merged_keys: tuple[KeyMaterialRecord, ...]
    provider_format: str
    already_migrated: bool

    def summary(self) -> dict[str, object]:
        return {
            "secret_vault_path": str(self.secret_vault_path),
            "key_provider_path": str(self.key_provider_path),
            "master_key_file": str(self.master_key_file),
            "vault_backup_path": str(self.vault_backup_path),
            "provider_backup_path": str(self.provider_backup_path),
            "vault_record_count": len(self.vault_records),
            "inline_key_count": len(self.inline_keys),
            "provider_key_count": len(self.provider_keys),
            "merged_key_count": len(self.merged_keys),
            "provider_format": self.provider_format,
            "already_migrated": self.already_migrated,
        }


def _aware_datetime(value: object, *, field_name: str) -> datetime:
    text = str(value or "").strip()
    if not text:
        raise RuntimeError(f"legacy inline key field {field_name} is required")
    parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise RuntimeError(f"legacy inline key field {field_name} must be timezone-aware")
    return parsed


def _optional_datetime(value: object, *, field_name: str) -> datetime | None:
    if value in {None, ""}:
        return None
    return _aware_datetime(value, field_name=field_name)


def _legacy_key_record(payload: Mapping[str, object]) -> KeyMaterialRecord:
    key_id = str(payload.get("key_id") or "").strip()
    encoded = str(payload.get("secret_b64") or "").strip()
    if not encoded:
        raise RuntimeError(f"legacy inline key {key_id or '<unknown>'} has no secret_b64")
    try:
        secret = base64.b64decode(encoded, validate=True)
    except Exception as exc:
        raise RuntimeError(f"legacy inline key {key_id or '<unknown>'} has invalid secret_b64") from exc
    record = KeyMaterialRecord(
        key_id=key_id,
        purpose=KeyPurpose(str(payload.get("purpose") or "")),
        secret_bytes=secret,
        tenant_id=None if payload.get("tenant_id") in {None, ""} else str(payload.get("tenant_id")),
        connector_id=None if payload.get("connector_id") in {None, ""} else str(payload.get("connector_id")),
        status=KeyStatus(str(payload.get("status") or KeyStatus.ACTIVE.value)),
        created_at=_aware_datetime(payload.get("created_at"), field_name="created_at"),
        activated_at=_aware_datetime(payload.get("activated_at"), field_name="activated_at"),
        expires_at=_optional_datetime(payload.get("expires_at"), field_name="expires_at"),
        metadata=dict(payload.get("metadata") or {}),
    )
    record.validate()
    return record


def _record_format(payload: Mapping[str, object]) -> str:
    has_legacy = bool(str(payload.get("secret_b64") or "").strip())
    has_wrapped = bool(str(payload.get("wrapped_secret") or "").strip())
    if has_legacy and not has_wrapped:
        return "legacy"
    if has_wrapped and not has_legacy:
        return "wrapped"
    return "invalid"


def _read_json_object(path: Path, *, label: str) -> dict[str, object]:
    if not path.is_file():
        raise RuntimeError(f"{label} file does not exist: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"{label} file cannot be read: {path}") from exc
    if not isinstance(payload, dict):
        raise RuntimeError(f"{label} payload must be a JSON object")
    return payload


def _same_key(left: KeyMaterialRecord, right: KeyMaterialRecord) -> bool:
    return (
        left.key_id == right.key_id
        and left.purpose is right.purpose
        and bytes(left.secret_bytes) == bytes(right.secret_bytes)
        and left.tenant_id == right.tenant_id
        and left.connector_id == right.connector_id
        and left.status is right.status
        and left.created_at == right.created_at
        and left.activated_at == right.activated_at
        and left.expires_at == right.expires_at
        and dict(left.metadata or {}) == dict(right.metadata or {})
    )


def _provider_records(
    *,
    path: Path,
    payload: Mapping[str, object],
    master_key: bytes,
) -> tuple[str, tuple[KeyMaterialRecord, ...]]:
    raw_records = payload.get("records")
    if not isinstance(raw_records, list):
        raise RuntimeError("key-provider payload records must be a list")
    if not raw_records:
        return "empty", ()
    if not all(isinstance(item, Mapping) for item in raw_records):
        raise RuntimeError("every key-provider record must be an object")
    records_payload = tuple(dict(item) for item in raw_records)
    formats = {_record_format(item) for item in records_payload}
    if formats == {"legacy"}:
        records = tuple(_legacy_key_record(item) for item in records_payload)
        return "legacy", records
    if formats == {"wrapped"}:
        with _master_key_environment(master_key):
            provider = FileKeyProvider(path=path)
            records = tuple(provider.get(str(item.get("key_id") or "")) for item in records_payload)
        return "wrapped", records
    raise RuntimeError("key-provider payload mixes legacy, wrapped, or invalid key record formats")


def _merge_keys(
    provider_keys: Sequence[KeyMaterialRecord],
    inline_keys: Sequence[KeyMaterialRecord],
) -> tuple[KeyMaterialRecord, ...]:
    merged: list[KeyMaterialRecord] = []
    by_id: dict[str, KeyMaterialRecord] = {}
    for record in (*provider_keys, *inline_keys):
        current = by_id.get(record.key_id)
        if current is None:
            by_id[record.key_id] = record
            merged.append(record)
            continue
        if not _same_key(current, record):
            raise RuntimeError(f"key_id collision has divergent key material or metadata: {record.key_id}")
    return tuple(merged)


def _validate_vault_records(
    records_payload: Sequence[Mapping[str, object]],
    *,
    key_provider,
) -> int:
    policy = EncryptionPolicy()
    verified = 0
    for item in records_payload:
        record = _deserialize_secret_record(dict(item))
        record.validate()
        record.ref.validate()
        key_id = str(record.metadata.get("encryption_key_id") or "").strip()
        if not key_id:
            raise RuntimeError("secret-vault record has no encryption_key_id")
        plaintext = decrypt_secret_payload(
            ciphertext=record.ciphertext,
            ref=record.ref,
            encryption_key_id=key_id,
            key_provider=key_provider,
            policy=policy,
            sealed_box_magic=InMemorySecretVault._SEALED_BOX_MAGIC,
        )
        if not isinstance(plaintext, bytes):
            raise RuntimeError("secret-vault decryption returned an unexpected payload type")
        del plaintext
        verified += 1
    return verified


def _atomic_temp_json(path: Path, payload: Mapping[str, object]) -> Path:
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.inline-key-migration-",
        suffix=".tmp",
        dir=str(path.parent),
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(dict(payload), handle, ensure_ascii=False, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary, 0o600)
        return temporary
    except Exception:
        temporary.unlink(missing_ok=True)
        raise


def _ensure_verified_backup(source: Path, backup: Path) -> bool:
    if backup.exists():
        if not filecmp.cmp(source, backup, shallow=False):
            raise RuntimeError(f"migration backup exists but differs from current source: {backup}")
        return False
    shutil.copy2(source, backup)
    os.chmod(backup, 0o600)
    if not filecmp.cmp(source, backup, shallow=False):
        raise RuntimeError(f"migration backup verification failed: {backup}")
    return True


def _fsync_parent(path: Path) -> None:
    descriptor = os.open(str(path.parent), os.O_DIRECTORY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def build_migration_plan(
    *,
    secret_vault_path: str | Path,
    key_provider_path: str | Path,
    master_key_file: str | Path,
) -> LegacyInlineVaultKeyMigrationPlan:
    vault_path = Path(secret_vault_path).expanduser().resolve()
    provider_path = Path(key_provider_path).expanduser().resolve()
    master_path = Path(master_key_file).expanduser().resolve()
    master_key = _read_master_key(master_path)
    vault_payload = _read_json_object(vault_path, label="secret-vault")
    provider_payload = _read_json_object(provider_path, label="key-provider")

    raw_records = vault_payload.get("records")
    raw_keys = vault_payload.get("keys")
    if not isinstance(raw_records, list):
        raise RuntimeError("secret-vault payload records must be a list")
    if raw_keys is None:
        raw_keys = []
    if not isinstance(raw_keys, list):
        raise RuntimeError("secret-vault payload keys must be a list")
    if not all(isinstance(item, Mapping) for item in raw_records):
        raise RuntimeError("every secret-vault record must be an object")
    if not all(isinstance(item, Mapping) for item in raw_keys):
        raise RuntimeError("every inline secret-vault key must be an object")

    vault_records = tuple(dict(item) for item in raw_records)
    inline_keys = tuple(_legacy_key_record(dict(item)) for item in raw_keys)
    provider_format, provider_keys = _provider_records(
        path=provider_path,
        payload=provider_payload,
        master_key=master_key,
    )
    merged_keys = _merge_keys(provider_keys, inline_keys)
    already_migrated = not inline_keys

    if already_migrated and provider_format == "wrapped":
        with _master_key_environment(master_key):
            provider = FileKeyProvider(path=provider_path)
            _validate_vault_records(vault_records, key_provider=provider)
    elif already_migrated:
        _validate_vault_records(vault_records, key_provider=InMemoryKeyProvider(records=provider_keys))
    else:
        _validate_vault_records(vault_records, key_provider=InMemoryKeyProvider(records=merged_keys))

    return LegacyInlineVaultKeyMigrationPlan(
        secret_vault_path=vault_path,
        key_provider_path=provider_path,
        master_key_file=master_path,
        vault_backup_path=vault_path.with_suffix(vault_path.suffix + ".legacy-inline-keys.bak"),
        provider_backup_path=provider_path.with_suffix(provider_path.suffix + ".pre-inline-vault-keys.bak"),
        vault_payload=vault_payload,
        provider_payload=provider_payload,
        vault_records=vault_records,
        inline_keys=inline_keys,
        provider_keys=provider_keys,
        merged_keys=merged_keys,
        provider_format=provider_format,
        already_migrated=already_migrated,
    )


def _validate_final_state(plan: LegacyInlineVaultKeyMigrationPlan, *, master_key: bytes) -> tuple[int, int]:
    with _master_key_environment(master_key):
        provider = FileKeyProvider(path=plan.key_provider_path)
        for expected in plan.merged_keys:
            loaded = provider.get(expected.key_id)
            if not _same_key(loaded, expected):
                raise RuntimeError(f"final key-provider record does not match source: {expected.key_id}")
        vault_payload = _read_json_object(plan.secret_vault_path, label="secret-vault")
        if vault_payload.get("keys"):
            raise RuntimeError("final secret-vault payload still contains inline keys")
        records = vault_payload.get("records")
        if not isinstance(records, list) or not all(isinstance(item, Mapping) for item in records):
            raise RuntimeError("final secret-vault records are invalid")
        secret_count = _validate_vault_records(tuple(dict(item) for item in records), key_provider=provider)
    return len(plan.merged_keys), secret_count


def apply_migration(plan: LegacyInlineVaultKeyMigrationPlan) -> dict[str, object]:
    master_key = _read_master_key(plan.master_key_file)
    if plan.already_migrated:
        if plan.provider_format != "wrapped":
            return {**plan.summary(), "applied": False, "vault_externalized": True}
        key_count, secret_count = _validate_final_state(plan, master_key=master_key)
        return {
            **plan.summary(),
            "applied": False,
            "validated_key_count": key_count,
            "validated_secret_count": secret_count,
        }

    migrated_provider = dict(plan.provider_payload)
    with _master_key_environment(master_key):
        migrated_provider["records"] = [_serialize_record(record) for record in plan.merged_keys]
    migrated_provider["inline_vault_key_migration"] = {
        "source": "secret_vault.inline_keys.secret_b64",
        "target": "external_key_provider.BAIOS-KE2",
        "inline_key_count": len(plan.inline_keys),
        "merged_key_count": len(plan.merged_keys),
        "vault_backup_path": str(plan.vault_backup_path),
        "provider_backup_path": str(plan.provider_backup_path),
    }

    migrated_vault = dict(plan.vault_payload)
    migrated_vault.pop("keys", None)
    migrated_vault["key_storage"] = "external_key_provider"
    migrated_vault["inline_key_migration"] = {
        "source": "inline_secret_b64_keys",
        "target": "external_key_provider",
        "key_count": len(plan.inline_keys),
        "provider_path": str(plan.key_provider_path),
    }

    provider_temporary = _atomic_temp_json(plan.key_provider_path, migrated_provider)
    vault_temporary = _atomic_temp_json(plan.secret_vault_path, migrated_vault)
    try:
        with _master_key_environment(master_key):
            staged_provider = FileKeyProvider(path=provider_temporary)
            for expected in plan.merged_keys:
                loaded = staged_provider.get(expected.key_id)
                if not _same_key(loaded, expected):
                    raise RuntimeError(f"staged key-provider record does not match source: {expected.key_id}")
            staged_secret_count = _validate_vault_records(plan.vault_records, key_provider=staged_provider)

        provider_backup_created = _ensure_verified_backup(plan.key_provider_path, plan.provider_backup_path)
        vault_backup_created = _ensure_verified_backup(plan.secret_vault_path, plan.vault_backup_path)

        os.replace(provider_temporary, plan.key_provider_path)
        os.chmod(plan.key_provider_path, 0o600)
        _fsync_parent(plan.key_provider_path)

        os.replace(vault_temporary, plan.secret_vault_path)
        os.chmod(plan.secret_vault_path, 0o600)
        _fsync_parent(plan.secret_vault_path)
    finally:
        provider_temporary.unlink(missing_ok=True)
        vault_temporary.unlink(missing_ok=True)

    key_count, secret_count = _validate_final_state(plan, master_key=master_key)
    if secret_count != staged_secret_count:
        raise RuntimeError("final secret-vault validation count differs from staged validation")
    return {
        **plan.summary(),
        "applied": True,
        "provider_backup_created": provider_backup_created,
        "vault_backup_created": vault_backup_created,
        "validated_key_count": key_count,
        "validated_secret_count": secret_count,
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Explicitly externalize legacy secret_vault.json inline secret_b64 keys "
            "into the canonical key provider and wrap the merged key set as BAIOS-KE2."
        )
    )
    parser.add_argument("--secret-vault-path", required=True)
    parser.add_argument("--key-provider-path", required=True)
    parser.add_argument("--master-key-file", required=True)
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Apply the migration. Without this flag the command is a read-only plan.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    plan = build_migration_plan(
        secret_vault_path=args.secret_vault_path,
        key_provider_path=args.key_provider_path,
        master_key_file=args.master_key_file,
    )
    result = apply_migration(plan) if args.apply else {**plan.summary(), "applied": False}
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
