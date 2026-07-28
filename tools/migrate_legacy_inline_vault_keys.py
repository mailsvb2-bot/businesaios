from __future__ import annotations

import argparse
import base64
import json
import os
import shutil
import tempfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping, Sequence

from security.key_management_contract import KeyMaterialRecord, KeyPurpose, KeyStatus
from security.key_provider import FileKeyProvider


@dataclass(frozen=True)
class LegacyVaultMigrationPlan:
    vault_path: Path
    key_provider_path: Path
    backup_path: Path
    key_records: tuple[KeyMaterialRecord, ...]
    vault_payload: Mapping[str, Any]

    def summary(self) -> dict[str, object]:
        return {
            "vault_path": str(self.vault_path),
            "key_provider_path": str(self.key_provider_path),
            "backup_path": str(self.backup_path),
            "key_count": len(self.key_records),
            "key_ids": [record.key_id for record in self.key_records],
            "will_remove_inline_keys": bool(self.key_records),
            "apply_required": True,
        }


def _parse_datetime(value: object, *, field_name: str) -> datetime:
    text = str(value or "").strip()
    if not text:
        raise RuntimeError(f"legacy key field {field_name} is required")
    parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise RuntimeError(f"legacy key field {field_name} must be timezone-aware")
    return parsed


def _parse_optional_datetime(value: object, *, field_name: str) -> datetime | None:
    if value in {None, ""}:
        return None
    return _parse_datetime(value, field_name=field_name)


def _legacy_key_record(payload: Mapping[str, object]) -> KeyMaterialRecord:
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
        created_at=_parse_datetime(payload.get("created_at"), field_name="created_at"),
        activated_at=_parse_datetime(payload.get("activated_at"), field_name="activated_at"),
        expires_at=_parse_optional_datetime(payload.get("expires_at"), field_name="expires_at"),
        metadata={**dict(payload.get("metadata") or {}), "migrated_from": "legacy_inline_secret_vault"},
    )
    record.validate()
    return record


def build_migration_plan(*, vault_path: str | Path, key_provider_path: str | Path) -> LegacyVaultMigrationPlan:
    source = Path(vault_path).expanduser().resolve()
    target = Path(key_provider_path).expanduser().resolve()
    if source == target:
        raise RuntimeError("vault and key-provider paths must be different")
    if not source.is_file():
        raise RuntimeError(f"legacy vault file does not exist: {source}")
    try:
        payload = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"legacy vault cannot be read: {source}") from exc
    if not isinstance(payload, dict):
        raise RuntimeError("legacy inline-key vault must be a JSON object")
    raw_keys = payload.get("keys")
    if not isinstance(raw_keys, list) or not raw_keys:
        raise RuntimeError("legacy vault contains no inline keys to migrate")
    records = tuple(_legacy_key_record(dict(item)) for item in raw_keys if isinstance(item, Mapping))
    if len(records) != len(raw_keys):
        raise RuntimeError("every legacy key entry must be an object")
    key_ids = [record.key_id for record in records]
    if len(key_ids) != len(set(key_ids)):
        raise RuntimeError("legacy vault contains duplicate key_id values")
    backup = source.with_suffix(source.suffix + ".legacy-inline-keys.bak")
    return LegacyVaultMigrationPlan(
        vault_path=source,
        key_provider_path=target,
        backup_path=backup,
        key_records=records,
        vault_payload=payload,
    )


def _atomic_write_json(path: Path, payload: Mapping[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(dict(payload), handle, ensure_ascii=False, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_name, path)
        try:
            os.chmod(path, 0o600)
        except OSError:
            pass
    finally:
        if os.path.exists(temporary_name):
            os.unlink(temporary_name)


def apply_migration(plan: LegacyVaultMigrationPlan) -> dict[str, object]:
    if plan.backup_path.exists():
        raise RuntimeError(f"migration backup already exists: {plan.backup_path}")
    plan.key_provider_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(plan.vault_path, plan.backup_path)
    try:
        os.chmod(plan.backup_path, 0o600)
    except OSError:
        pass

    provider = FileKeyProvider(path=plan.key_provider_path)
    for record in plan.key_records:
        try:
            existing = provider.get(record.key_id)
        except KeyError:
            provider.register(record)
            continue
        if (
            existing.secret_bytes != record.secret_bytes
            or existing.purpose is not record.purpose
            or existing.tenant_id != record.tenant_id
            or existing.connector_id != record.connector_id
        ):
            raise RuntimeError(f"target key provider contains a conflicting key: {record.key_id}")

    migrated_payload = {
        key: value
        for key, value in dict(plan.vault_payload).items()
        if key != "keys"
    }
    migrated_payload["key_storage"] = "external_key_provider"
    migrated_payload["migration"] = {
        "source": "legacy_inline_secret_vault",
        "key_count": len(plan.key_records),
        "backup_path": str(plan.backup_path),
    }
    _atomic_write_json(plan.vault_path, migrated_payload)
    return {
        **plan.summary(),
        "applied": True,
        "backup_created": plan.backup_path.is_file(),
        "inline_keys_removed": "keys" not in migrated_payload,
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Move legacy inline secret-vault keys into the wrapped external FileKeyProvider.",
    )
    parser.add_argument("--vault-path", required=True, help="Path to legacy secret_vault.json")
    parser.add_argument("--key-provider-path", required=True, help="Destination key_provider.json")
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Apply the migration. Without this flag the command is a read-only dry run.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    plan = build_migration_plan(
        vault_path=args.vault_path,
        key_provider_path=args.key_provider_path,
    )
    result = apply_migration(plan) if args.apply else {**plan.summary(), "applied": False}
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
