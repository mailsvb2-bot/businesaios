from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from threading import RLock

from .policy_manifest import PolicyManifest

CANON_SAFETY_POLICY_TRUST_CHAIN = True


@dataclass(frozen=True)
class PolicyTrustRecord:
    version_id: str
    tenant_id: str
    policy_scope: str
    fingerprint: str
    parent_fingerprint: str = ''
    signature: str = ''
    source: str = ''
    key_id: str = ''
    chain_index: int = 0
    chain_hash: str = ''


@dataclass(frozen=True)
class PolicyTrustSnapshot:
    tenant_id: str
    policy_scope: str
    chain_index: int
    chain_hash: str
    fingerprint: str
    record_count: int = 0
    snapshot_hash: str = ''


class PolicyTrustChain:
    def __init__(self, *, path: str | None = None, snapshot_path: str | None = None) -> None:
        self._path = Path(path) if path else None
        self._snapshot_path = Path(snapshot_path) if snapshot_path else None
        if self._path is not None:
            self._path.parent.mkdir(parents=True, exist_ok=True)
        if self._snapshot_path is not None:
            self._snapshot_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = RLock()
        self._records: dict[tuple[str, str], list[PolicyTrustRecord]] = {}
        self._snapshots: dict[tuple[str, str], PolicyTrustSnapshot] = {}
        self._load()
        self._load_snapshots()

    def append(self, manifest: PolicyManifest) -> PolicyTrustRecord:
        key = (str(manifest.tenant_id), str(manifest.policy_scope))
        with self._lock:
            parent = self.latest(tenant_id=manifest.tenant_id, policy_scope=manifest.policy_scope)
            chain_index = 0 if parent is None else int(parent.chain_index) + 1
            parent_hash = '' if parent is None else str(parent.chain_hash)
            record = PolicyTrustRecord(
                version_id=str(manifest.version_id),
                tenant_id=str(manifest.tenant_id),
                policy_scope=str(manifest.policy_scope),
                fingerprint=self._record_fingerprint(manifest),
                parent_fingerprint='' if parent is None else str(parent.fingerprint),
                signature=str(manifest.signature),
                source=str(manifest.source),
                key_id=str(manifest.key_id or ''),
                chain_index=chain_index,
                chain_hash=self._chain_hash(parent_hash=parent_hash, manifest=manifest, chain_index=chain_index),
            )
            chain = self._records.setdefault(key, [])
            if chain and chain[-1].fingerprint == record.fingerprint and chain[-1].chain_hash == record.chain_hash:
                return chain[-1]
            chain.append(record)
            self._persist(record)
            self._persist_snapshot(record)
            return record

    def latest(self, *, tenant_id: str, policy_scope: str) -> PolicyTrustRecord | None:
        chain = self._records.get((str(tenant_id), str(policy_scope)), [])
        return chain[-1] if chain else None

    def latest_snapshot(self, *, tenant_id: str, policy_scope: str) -> PolicyTrustSnapshot | None:
        return self._snapshots.get((str(tenant_id), str(policy_scope)))

    def lineage(self, *, tenant_id: str, policy_scope: str) -> tuple[PolicyTrustRecord, ...]:
        return tuple(self._records.get((str(tenant_id), str(policy_scope)), []))

    def verify_lineage(self, *, tenant_id: str, policy_scope: str) -> bool:
        expected_parent_fingerprint = ''
        expected_chain_hash = ''
        expected_index = 0
        chain = self.lineage(tenant_id=tenant_id, policy_scope=policy_scope)
        for record in chain:
            if str(record.parent_fingerprint or '') != expected_parent_fingerprint:
                return False
            if int(record.chain_index) != expected_index:
                return False
            computed = hashlib.sha256(
                json.dumps(
                    {
                        'parent_chain_hash': expected_chain_hash,
                        'tenant_id': str(record.tenant_id),
                        'policy_scope': str(record.policy_scope),
                        'fingerprint': str(record.fingerprint),
                        'signature': str(record.signature),
                        'version_id': str(record.version_id),
                        'source': str(record.source),
                        'key_id': str(record.key_id),
                        'chain_index': int(record.chain_index),
                    },
                    sort_keys=True,
                    separators=(',', ':'),
                ).encode('utf-8')
            ).hexdigest()
            if str(record.chain_hash or '') != computed:
                return False
            expected_parent_fingerprint = str(record.fingerprint)
            expected_chain_hash = str(record.chain_hash)
            expected_index += 1
        snapshot = self.latest_snapshot(tenant_id=tenant_id, policy_scope=policy_scope)
        if snapshot is not None:
            latest = chain[-1] if chain else None
            if latest is None:
                return False
            if int(snapshot.chain_index) != int(latest.chain_index):
                return False
            if str(snapshot.chain_hash) != str(latest.chain_hash):
                return False
            if str(snapshot.fingerprint) != str(latest.fingerprint):
                return False
            if int(snapshot.record_count or 0) != len(chain):
                return False
            if str(snapshot.snapshot_hash or '') != self._snapshot_hash(snapshot):
                return False
        return True

    def verify_all(self) -> bool:
        record_keys = set(self._records.keys())
        snapshot_keys = set(self._snapshots.keys())
        if snapshot_keys - record_keys:
            return False
        return all(
            self.verify_lineage(tenant_id=tenant_id, policy_scope=scope)
            for (tenant_id, scope) in record_keys
        )

    @staticmethod
    def _record_fingerprint(manifest: PolicyManifest) -> str:
        material = json.dumps(
            {
                'tenant_id': str(manifest.tenant_id),
                'policy_scope': str(manifest.policy_scope),
                'policy_payload': dict(manifest.policy_payload),
                'signature': str(manifest.signature),
                'version_id': str(manifest.version_id),
                'source': str(manifest.source),
                'key_id': str(manifest.key_id or ''),
                'issued_at': str(manifest.issued_at or ''),
            },
            sort_keys=True,
            separators=(',', ':'),
            default=str,
        ).encode('utf-8')
        return hashlib.sha256(material).hexdigest()

    @staticmethod
    def _chain_hash(*, parent_hash: str, manifest: PolicyManifest, chain_index: int) -> str:
        material = json.dumps(
            {
                'parent_chain_hash': str(parent_hash or ''),
                'tenant_id': str(manifest.tenant_id),
                'policy_scope': str(manifest.policy_scope),
                'fingerprint': PolicyTrustChain._record_fingerprint(manifest),
                'signature': str(manifest.signature),
                'version_id': str(manifest.version_id),
                'source': str(manifest.source),
                'key_id': str(manifest.key_id or ''),
                'chain_index': int(chain_index),
            },
            sort_keys=True,
            separators=(',', ':'),
            default=str,
        ).encode('utf-8')
        return hashlib.sha256(material).hexdigest()

    def _load(self) -> None:
        if self._path is None or not self._path.exists():
            return
        for line in self._path.read_text(encoding='utf-8').splitlines():
            text = str(line).strip()
            if not text:
                continue
            data = json.loads(text)
            record = PolicyTrustRecord(
                version_id=str(data.get('version_id', '')),
                tenant_id=str(data.get('tenant_id', '')),
                policy_scope=str(data.get('policy_scope', '')),
                fingerprint=str(data.get('fingerprint', '')),
                parent_fingerprint=str(data.get('parent_fingerprint', '')),
                signature=str(data.get('signature', '')),
                source=str(data.get('source', '')),
                key_id=str(data.get('key_id', '')),
                chain_index=int(data.get('chain_index', 0) or 0),
                chain_hash=str(data.get('chain_hash', '')),
            )
            self._records.setdefault((record.tenant_id, record.policy_scope), []).append(record)

    def _load_snapshots(self) -> None:
        if self._snapshot_path is None or not self._snapshot_path.exists():
            return
        for line in self._snapshot_path.read_text(encoding='utf-8').splitlines():
            text = str(line).strip()
            if not text:
                continue
            data = json.loads(text)
            snapshot = PolicyTrustSnapshot(
                tenant_id=str(data.get('tenant_id', '')),
                policy_scope=str(data.get('policy_scope', '')),
                chain_index=int(data.get('chain_index', 0) or 0),
                chain_hash=str(data.get('chain_hash', '')),
                fingerprint=str(data.get('fingerprint', '')),
                record_count=int(data.get('record_count', 0) or 0),
                snapshot_hash=str(data.get('snapshot_hash', '')),
            )
            self._snapshots[(snapshot.tenant_id, snapshot.policy_scope)] = snapshot

    def _persist(self, record: PolicyTrustRecord) -> None:
        if self._path is None:
            return
        with self._path.open('a', encoding='utf-8') as fh:
            fh.write(json.dumps(asdict(record), sort_keys=True, ensure_ascii=False) + "\n")

    def _persist_snapshot(self, record: PolicyTrustRecord) -> None:
        snapshot = PolicyTrustSnapshot(
            tenant_id=record.tenant_id,
            policy_scope=record.policy_scope,
            chain_index=record.chain_index,
            chain_hash=record.chain_hash,
            fingerprint=record.fingerprint,
            record_count=len(self._records.get((record.tenant_id, record.policy_scope), [])),
        )
        snapshot = PolicyTrustSnapshot(**{**asdict(snapshot), 'snapshot_hash': self._snapshot_hash(snapshot)})
        self._snapshots[(snapshot.tenant_id, snapshot.policy_scope)] = snapshot
        if self._snapshot_path is None:
            return
        with self._snapshot_path.open('a', encoding='utf-8') as fh:
            fh.write(json.dumps(asdict(snapshot), sort_keys=True, ensure_ascii=False) + "\n")


    @staticmethod
    def _snapshot_hash(snapshot: PolicyTrustSnapshot) -> str:
        return hashlib.sha256(json.dumps({'tenant_id': snapshot.tenant_id, 'policy_scope': snapshot.policy_scope, 'chain_index': int(snapshot.chain_index), 'chain_hash': snapshot.chain_hash, 'fingerprint': snapshot.fingerprint, 'record_count': int(snapshot.record_count)}, sort_keys=True, separators=(',', ':')).encode('utf-8')).hexdigest()


__all__ = ['CANON_SAFETY_POLICY_TRUST_CHAIN', 'PolicyTrustChain', 'PolicyTrustRecord', 'PolicyTrustSnapshot']
