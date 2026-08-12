from __future__ import annotations

import argparse
import base64
import filecmp
import json
import os
import shutil
import tempfile
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterator, Mapping, Sequence

from security.key_management_contract import KeyMaterialRecord, KeyPurpose, KeyStatus
from security.key_provider import FileKeyProvider, _serialize_record
from security.secret_vault import FileSecretVault


@dataclass(frozen=True)
class LegacyKeyProviderMigrationPlan:
    key_provider_path: Path
    secret_vault_path: Path | None
    master_key_file: Path
    backup_path: Path
    records: tuple[KeyMaterialRecord, ...]
    payload: Mapping[str, object]
    already_migrated: bool

    def summary(self) -> dict[str, object]:
        return {
            "key_provider_path": str(self.key_provider_path),
            "secret_vault_path": None if self.secret_vault_path is None else str(self.secret_vault_path),
            "backup_path": str(self.backup_path),
            "key_count": len(self.records),
            "already_migrated": self.already_migrated,
        }


def _aware_datetime(value: object, *, field_name: str) -> datetime:
    text = str(value or "").strip()
    if not text:
        raise RuntimeError(f"legacy key field {field_name} is required")
    parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise RuntimeError(f"legacy key field {field_name} must be timezone-aware")
    return parsed


def _optional_datetime(value: object, *, field_name: str) -> datetime | None:
    if value in {None, ""}:
        return None
    return _aware_datetime(value, field_name=field_name)


def _legacy_record(payload: Mapping[str, object]) -> KeyMaterialRecord:
    key_id = str(payload.get("key_id") or "").strip()
    encoded = str(payload.get("secret_b64") or "").strip()
    if not encoded:
        raise RuntimeError(f"legacy key {key_id or '<unknown>'} has no secret_b64")
    try:
        secret = base64.b64decode(encoded, validate=True)
    except Exception as exc:
        raise RuntimeError(f"legacy key {key_id or '<unknown>'} has invalid secret_b64") from exc
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


def _read_master_key(path: Path) -> bytes:
    if not path.is_file():
        raise RuntimeError(f"master key file does not exist: {path}")
    key = path.read_bytes()
    if len(key) != 32:
        raise RuntimeError("master key file must contain exactly 32 bytes")
    return key


@contextmanager
def _master_key_environment(master_key: bytes) -> Iterator[None]:
    name = "BUSINESAIOS_KEY_PROVIDER_MASTER_KEY_B64"
    encoded = base64.b64encode(master_key).decode("ascii")
    previous = os.environ.get(name)
    if previous:
        try:
            existing = base64.b64decode(previous, validate=True)
        except Exception as exc:
            raise RuntimeError(f"existing {name} is invalid") from exc
        if existing != master_key:
            raise RuntimeError(f"existing {name} does not match --master-key-file")
    os.environ[name] = encoded
    try:
        yield
    finally:
        if previous is None:
            os.environ.pop(name, None)
        else:
            os.environ[name] = previous


def build_migration_plan(
    *,
    key_provider_path: str | Path,
    master_key_file: str | Path,
    secret_vault_path: str | Path | None = None,
) -> LegacyKeyProviderMigrationPlan:
    provider_path = Path(key_provider_path).expanduser().resolve()
    master_path = Path(master_key_file).expanduser().resolve()
    vault_path = None if secret_vault_path is None else Path(secret_vault_path).expanduser().resolve()
    if not provider_path.is_file():
        raise RuntimeError(f"key-provider file does not exist: {provider_path}")
    if vault_path is not None and not vault_path.is_file():
        raise RuntimeError(f"secret-vault file does not exist: {vault_path}")
    _read_master_key(master_path)
    try:
        payload = json.loads(provider_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"key-provider file cannot be read: {provider_path}") from exc
    if not isinstance(payload, dict):
        raise RuntimeError("key-provider payload must be a JSON object")
    raw_records = payload.get("records")
    if not isinstance(raw_records, list) or not raw_records:
        raise RuntimeError("key-provider payload contains no records")
    if not all(isinstance(item, Mapping) for item in raw_records):
        raise RuntimeError("every key-provider record must be an object")
    record_payloads = tuple(dict(item) for item in raw_records)
    formats = {_record_format(item) for item in record_payloads}
    if formats == {"wrapped"}:
        records: tuple[KeyMaterialRecord, ...] = ()
        already_migrated = True
    elif formats == {"legacy"}:
        records = tuple(_legacy_record(item) for item in record_payloads)
        key_ids = [record.key_id for record in records]
        if len(key_ids) != len(set(key_ids)):
            raise RuntimeError("key-provider payload contains duplicate key_id values")
        already_migrated = False
    else:
        raise RuntimeError("key-provider payload mixes legacy, wrapped, or invalid key record formats")
    backup = provider_path.with_suffix(provider_path.suffix + ".legacy-secret-b64.bak")
    return LegacyKeyProviderMigrationPlan(
        key_provider_path=provider_path,
        secret_vault_path=vault_path,
        master_key_file=master_path,
        backup_path=backup,
        records=records,
        payload=payload,
        already_migrated=already_migrated,
    )


def _atomic_temp_json(path: Path, payload: Mapping[str, object]) -> Path:
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.migration-",
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


def _validate_provider(provider: FileKeyProvider, expected: Sequence[KeyMaterialRecord] | None) -> int:
    if expected is None:
        return len(getattr(provider, "_records", {}))
    for source in expected:
        loaded = provider.get(source.key_id)
        if (
            bytes(loaded.secret_bytes) != bytes(source.secret_bytes)
            or loaded.purpose is not source.purpose
            or loaded.tenant_id != source.tenant_id
            or loaded.connector_id != source.connector_id
            or loaded.status is not source.status
            or loaded.created_at != source.created_at
            or loaded.activated_at != source.activated_at
            or loaded.expires_at != source.expires_at
            or dict(loaded.metadata or {}) != dict(source.metadata or {})
        ):
            raise RuntimeError(f"migrated key record does not match source metadata: {source.key_id}")
    return len(expected)


def _validate_vault(vault_path: Path | None, provider: FileKeyProvider) -> int:
    if vault_path is None:
        return 0
    if vault_path.name != "secret_vault.json":
        raise RuntimeError("secret-vault validation requires a file named secret_vault.json")
    vault = FileSecretVault(root_dir=vault_path.parent, key_provider=provider)
    verified = 0
    for record in vault.list_records():
        key_id = str(record.metadata.get("encryption_key_id") or "").strip()
        if not key_id:
            raise RuntimeError("secret-vault record has no encryption_key_id")
        plaintext = vault._decrypt(
            record.ciphertext,
            ref=record.ref,
            encryption_key_id=key_id,
        )
        if not isinstance(plaintext, bytes):
            raise RuntimeError("secret-vault decryption returned an unexpected payload type")
        del plaintext
        verified += 1
    return verified


def apply_migration(plan: LegacyKeyProviderMigrationPlan) -> dict[str, object]:
    master_key = _read_master_key(plan.master_key_file)
    with _master_key_environment(master_key):
        if plan.already_migrated:
            provider = FileKeyProvider(path=plan.key_provider_path)
            key_count = _validate_provider(provider, None)
            secret_count = _validate_vault(plan.secret_vault_path, provider)
            return {
                **plan.summary(),
                "applied": False,
                "validated_key_count": key_count,
                "validated_secret_count": secret_count,
            }

        if plan.backup_path.exists():
            raise RuntimeError(f"migration backup already exists: {plan.backup_path}")
        shutil.copy2(plan.key_provider_path, plan.backup_path)
        os.chmod(plan.backup_path, 0o600)
        if not filecmp.cmp(plan.key_provider_path, plan.backup_path, shallow=False):
            raise RuntimeError("key-provider backup verification failed")

        migrated_payload = dict(plan.payload)
        migrated_payload["records"] = [_serialize_record(record) for record in plan.records]
        migrated_payload["migration"] = {
            "source": "legacy_plaintext_secret_b64",
            "target": "BAIOS-KE2",
            "key_count": len(plan.records),
            "backup_path": str(plan.backup_path),
        }
        temporary = _atomic_temp_json(plan.key_provider_path, migrated_payload)
        try:
            provider = FileKeyProvider(path=temporary)
            key_count = _validate_provider(provider, plan.records)
            secret_count = _validate_vault(plan.secret_vault_path, provider)
            os.replace(temporary, plan.key_provider_path)
            os.chmod(plan.key_provider_path, 0o600)
            directory_fd = os.open(str(plan.key_provider_path.parent), os.O_DIRECTORY)
            try:
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)
        finally:
            temporary.unlink(missing_ok=True)

        final_provider = FileKeyProvider(path=plan.key_provider_path)
        _validate_provider(final_provider, plan.records)
        _validate_vault(plan.secret_vault_path, final_provider)
        return {
            **plan.summary(),
            "applied": True,
            "backup_created": plan.backup_path.is_file(),
            "validated_key_count": key_count,
            "validated_secret_count": secret_count,
        }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Explicitly migrate legacy plaintext key_provider.json secret_b64 records "
            "to authenticated BAIOS-KE2 envelopes."
        )
    )
    parser.add_argument("--key-provider-path", required=True)
    parser.add_argument("--master-key-file", required=True)
    parser.add_argument(
        "--secret-vault-path",
        help="Optional secret_vault.json to decrypt-validate before replacing the key-provider file.",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Apply the migration. Without this flag the command is a read-only plan.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    plan = build_migration_plan(
        key_provider_path=args.key_provider_path,
        master_key_file=args.master_key_file,
        secret_vault_path=args.secret_vault_path,
    )
    result = apply_migration(plan) if args.apply else {**plan.summary(), "applied": False}
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
