from __future__ import annotations

import importlib
import json
from datetime import UTC, datetime
from typing import Any, Optional

from kernel.decision_crypto import assert_envelope_signature_surface, signed_material_for_archive
from core.utils.canonical import payload_hash as canonical_payload_hash
from storage.sqlite_fallback import SqliteSessionFactory
from storage.tenant_partitioning import build_partition_key, normalize_storage_tenant_id


CANON_SQLITE_DECISION_ARCHIVE = True


def _utc_now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _materialize_archive_payload(env: Any) -> dict[str, Any]:
    assert_envelope_signature_surface(env)
    signed = signed_material_for_archive(env)
    return {
        "decision": dict(env.decision.__dict__),
        "payload_hash": signed["payload_hash"],
        "signature": signed["signature"],
        "kid": signed["kid"],
        "envelope_version": int(getattr(env, "envelope_version", 1)),
        "policy_version": getattr(env, "policy_version", None),
        "rollout_group": getattr(env, "rollout_group", None),
        "canary_flag": bool(getattr(env, "canary_flag", False)),
        "signature_alg": signed["signature_alg"],
    }


def _rebuild_envelope(data: dict[str, Any]) -> Any:
    mod = importlib.import_module("core.ai.decision")
    Decision = getattr(mod, "Decision")
    DecisionEnvelope = getattr(mod, "DecisionEnvelope")
    decision = Decision(**data["decision"])
    payload_hash_value = str(data.get("payload_hash", "") or "")
    if not payload_hash_value:
        payload_hash_value = canonical_payload_hash(getattr(decision, "payload", {}) or {})
    return DecisionEnvelope(
        decision=decision,
        payload_hash=payload_hash_value,
        signature=data["signature"],
        kid=data["kid"],
        envelope_version=int(data.get("envelope_version", 1)),
        policy_version=data.get("policy_version"),
        rollout_group=data.get("rollout_group"),
        canary_flag=bool(data.get("canary_flag", False)),
    )


class SqliteDecisionArchive:
    """Dev deterministic replay archive with storage metadata hardening."""

    def __init__(self, path: str, *, tenant_id: str | None = None):
        self._path = str(path)
        self._tenant_id = normalize_storage_tenant_id(tenant_id)
        self._partition_key = build_partition_key(self._tenant_id, scope="decision_archive")
        self._session_factory = SqliteSessionFactory(self._path, wal=True, busy_timeout_ms=5000, synchronous="NORMAL")
        self._session = None

    def __enter__(self):
        self._session = self._session_factory.open().__enter__()
        self._init_schema()
        return self

    def __exit__(self, exc_type, exc, tb):
        if self._session is not None:
            self._session.__exit__(exc_type, exc, tb)
            self._session = None

    @property
    def _db(self):
        if self._session is None:
            raise RuntimeError("sqlite decision archive is not open")
        return self._session

    def _init_schema(self) -> None:
        self._db.execute(
            """
            CREATE TABLE IF NOT EXISTS decision_archive (
                decision_id TEXT PRIMARY KEY,
                tenant_id TEXT NOT NULL,
                partition_key TEXT NOT NULL,
                envelope_json TEXT NOT NULL,
                payload_sha256 TEXT NOT NULL,
                signature_kid TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        self._db.execute("CREATE INDEX IF NOT EXISTS idx_decision_archive_partition_key ON decision_archive(partition_key)")
        self._db.execute("CREATE INDEX IF NOT EXISTS idx_decision_archive_tenant_id ON decision_archive(tenant_id)")
        self._db.execute("CREATE INDEX IF NOT EXISTS idx_decision_archive_updated_at ON decision_archive(updated_at)")
        self._db.commit()

    def put(self, env: Any) -> None:
        payload = _materialize_archive_payload(env)
        env_json = json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
        now_iso = _utc_now_iso()
        self._db.execute(
            """
            INSERT INTO decision_archive(
                decision_id,
                tenant_id,
                partition_key,
                envelope_json,
                payload_sha256,
                signature_kid,
                created_at,
                updated_at
            ) VALUES(?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(decision_id) DO UPDATE SET
                tenant_id=excluded.tenant_id,
                partition_key=excluded.partition_key,
                envelope_json=excluded.envelope_json,
                payload_sha256=excluded.payload_sha256,
                signature_kid=excluded.signature_kid,
                updated_at=excluded.updated_at
            """,
            (
                str(env.decision.decision_id),
                self._tenant_id,
                self._partition_key,
                env_json,
                str(payload.get("payload_hash") or ""),
                str(payload.get("kid") or ""),
                now_iso,
                now_iso,
            ),
        )
        self._db.commit()

    def get(self, decision_id: str) -> Optional[Any]:
        row = self._db.fetchone("SELECT envelope_json FROM decision_archive WHERE decision_id = ?", (str(decision_id),))
        if not row:
            return None
        return _rebuild_envelope(json.loads(str(row[0] or "{}")))

    def ping(self) -> bool:
        try:
            return self._db.fetchone("SELECT 1") is not None
        except Exception:
            return False
