from __future__ import annotations

import base64
import json
from concurrent.futures import ThreadPoolExecutor

import pytest

from runtime.business_autonomy.bootstrap import _build_distributed_state
from runtime.business_autonomy.sqlite_distributed_state import (
    SQLiteDistributedCompareAndSwap,
    SQLiteDistributedDocumentStore,
    SQLiteDistributedSequenceStore,
    SQLiteStateDatabase,
)
from security.key_envelope import unwrap_key_material, wrap_key_material
from security.key_management_contract import KeyPurpose
from security.key_provider import FileKeyProvider
from security.secret_contract import SecretRef, SecretSource
from security.secret_vault import FileSecretVault


def test_sqlite_cas_create_is_atomic_across_instances(tmp_path) -> None:
    database = SQLiteStateDatabase(tmp_path / "state.sqlite3")
    stores = [SQLiteDistributedCompareAndSwap(database, scope="test") for _ in range(16)]

    with ThreadPoolExecutor(max_workers=16) as pool:
        outcomes = list(
            pool.map(
                lambda store: store.create_if_absent(key="idem-a", payload={"state": "started"}),
                stores,
            )
        )

    assert outcomes.count(True) == 1
    assert outcomes.count(False) == 15


def test_sqlite_sequence_is_unique_across_instances(tmp_path) -> None:
    database = SQLiteStateDatabase(tmp_path / "state.sqlite3")
    stores = [SQLiteDistributedSequenceStore(database) for _ in range(8)]

    with ThreadPoolExecutor(max_workers=8) as pool:
        values = list(pool.map(lambda store: store.next_value(namespace="fence"), stores * 8))

    assert sorted(values) == list(range(1, 65))


def test_sqlite_document_cas_rejects_stale_writer(tmp_path) -> None:
    database = SQLiteStateDatabase(tmp_path / "state.sqlite3")
    first = SQLiteDistributedDocumentStore(database)
    second = SQLiteDistributedDocumentStore(database)

    version = first.put(collection="records", document_id="a", payload={"value": 1})
    assert version == 1
    assert first.put(collection="records", document_id="a", payload={"value": 2}, expected_version=1) == 2
    with pytest.raises(ValueError, match="version mismatch"):
        second.put(collection="records", document_id="a", payload={"value": 3}, expected_version=1)


def test_multi_replica_sqlite_runtime_fails_closed(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.setenv("BUSINESAIOS_RUNTIME_REPLICA_COUNT", "2")

    with pytest.raises(RuntimeError, match="MULTI_REPLICA"):
        _build_distributed_state()


def test_key_envelope_requires_the_same_external_master(monkeypatch, tmp_path) -> None:
    master_a = bytes(range(32))
    master_b = bytes(reversed(range(32)))
    monkeypatch.setenv("BUSINESAIOS_KEY_PROVIDER_MASTER_KEY_B64", base64.b64encode(master_a).decode("ascii"))

    wrapped = wrap_key_material(
        b"secret-key-material",
        key_id="key-a",
        purpose=KeyPurpose.SECRET_ENCRYPTION.value,
        tenant_id="tenant-a",
        connector_id="connector-a",
    )
    assert unwrap_key_material(
        wrapped,
        key_id="key-a",
        purpose=KeyPurpose.SECRET_ENCRYPTION.value,
        tenant_id="tenant-a",
        connector_id="connector-a",
    ) == b"secret-key-material"

    monkeypatch.setenv("BUSINESAIOS_KEY_PROVIDER_MASTER_KEY_B64", base64.b64encode(master_b).decode("ascii"))
    with pytest.raises(RuntimeError, match="integrity"):
        unwrap_key_material(
            wrapped,
            key_id="key-a",
            purpose=KeyPurpose.SECRET_ENCRYPTION.value,
            tenant_id="tenant-a",
            connector_id="connector-a",
        )


def test_file_key_provider_never_persists_plaintext_key(monkeypatch, tmp_path) -> None:
    master = bytes(range(32))
    monkeypatch.setenv("BUSINESAIOS_KEY_PROVIDER_MASTER_KEY_B64", base64.b64encode(master).decode("ascii"))
    path = tmp_path / "key_provider.json"
    provider = FileKeyProvider(path=path)
    record = provider.issue_key(
        key_id="key-a",
        purpose=KeyPurpose.SECRET_ENCRYPTION,
        tenant_id="tenant-a",
        connector_id="connector-a",
    )

    raw = path.read_text(encoding="utf-8")
    payload = json.loads(raw)

    assert base64.b64encode(record.secret_bytes).decode("ascii") not in raw
    assert "wrapped_secret" in payload["records"][0]
    assert "secret_b64" not in payload["records"][0]
    assert FileKeyProvider(path=path).get("key-a").secret_bytes == record.secret_bytes


def test_file_vault_does_not_embed_decryption_keys(monkeypatch, tmp_path) -> None:
    master = bytes(range(32))
    monkeypatch.setenv("BUSINESAIOS_KEY_PROVIDER_MASTER_KEY_B64", base64.b64encode(master).decode("ascii"))
    key_provider = FileKeyProvider(path=tmp_path / "key_provider.json")
    vault = FileSecretVault(root_dir=tmp_path / "vault", key_provider=key_provider)
    ref = SecretRef(
        tenant_id="tenant-a",
        secret_name="telegram-token",
        connector_id="connector-a",
    )

    vault.seed_plaintext(ref=ref, plaintext="123:token", source=SecretSource.MEMORY)
    payload = json.loads((tmp_path / "vault" / "secret_vault.json").read_text(encoding="utf-8"))

    assert "keys" not in payload
    assert payload["key_storage"] == "external_key_provider"
    assert vault.get(ref) == b"123:token"


def test_production_without_external_master_key_fails(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("BUSINESAIOS_KEY_PROVIDER_BACKEND", "file")
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.delenv("BUSINESAIOS_KEY_PROVIDER_MASTER_KEY_B64", raising=False)
    monkeypatch.delenv("BUSINESAIOS_KEY_PROVIDER_MASTER_KEY_PATH", raising=False)

    from security.key_provider import build_default_key_provider

    with pytest.raises(RuntimeError, match="PRODUCTION_KEY_PROVIDER_MASTER_KEY_REQUIRED"):
        build_default_key_provider()
