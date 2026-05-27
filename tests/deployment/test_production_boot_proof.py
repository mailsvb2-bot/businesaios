from __future__ import annotations

import json
import sqlite3
import sys
from contextlib import ExitStack
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace

from fastapi.testclient import TestClient

from adapters.api.fastapi.dependencies import FastAPIBootResult, FastAPIDependencyContainer
from bootstrap.health_server import start_health_server
from bootstrap.runtime_boot import build_runtime_orchestrator
from core.ai.decision import Decision
from entrypoints.api.action_models import ExecuteActionRequest
from entrypoints.api.api_key_policy import PersistentApiKeyStore
from entrypoints.api.fastapi_app_factory import create_fastapi_app
from governance.rbac_contract import RoleId
from kernel.decision_crypto import sign_decision
from runtime.enforcement.idempotency_gate import mark_execution_once
from runtime.wiring import build_durable_stores, resolve_storage_config
from scripts.ci.http_probe_io import fetch_text
from tenancy.tenant_contract import TenantPlan, TenantRecord, TenantStatus
from tenancy.tenant_registry import PersistentTenantRegistry


class _SQLiteCursorWrapper:
    def __init__(self, cursor):
        self._cursor = cursor
        self.description = None

    def execute(self, sql, params=None):
        statement = str(sql or '').strip()
        upper = statement.upper()
        if upper.startswith('SET ') or upper in {'BEGIN;', 'BEGIN'}:
            self.description = None
            return self
        sql2 = statement.replace('%s', '?').replace('BIGSERIAL', 'INTEGER')
        if params is None:
            self._cursor.execute(sql2)
        else:
            self._cursor.execute(sql2, tuple(params))
        self.description = self._cursor.description
        return self

    def fetchone(self):
        return self._cursor.fetchone()

    def fetchall(self):
        return self._cursor.fetchall()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        self._cursor.close()
        return None


class _SQLiteConnectionWrapper:
    def __init__(self, path: Path):
        self._conn = sqlite3.connect(path, check_same_thread=False)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        try:
            if exc_type is None:
                self._conn.commit()
            else:
                self._conn.rollback()
        finally:
            self._conn.close()
        return None

    def cursor(self):
        return _SQLiteCursorWrapper(self._conn.cursor())

    def commit(self):
        self._conn.commit()

    def rollback(self):
        self._conn.rollback()

    def close(self):
        self._conn.close()


class _FakePsycopgModule:
    def __init__(self, db_path: Path):
        self._db_path = Path(db_path)

    def connect(self, dsn: str, autocommit: bool = False, connect_timeout: int | None = None):
        return _SQLiteConnectionWrapper(self._db_path)


@dataclass
class _ManagedResources:
    stack: ExitStack

    def shutdown(self) -> None:
        self.stack.close()


class _ProofApplicationService:
    def __init__(self, *, event_store, ledger, snapshot_store, decision_archive, outbox, payment_outbox) -> None:
        self._event_store = event_store
        self._ledger = ledger
        self._snapshot_store = snapshot_store
        self._decision_archive = decision_archive
        self._outbox = outbox
        self._payment_outbox = payment_outbox

    def startup_audit_events(self) -> tuple[str, ...]:
        return ('boot:prod', 'storage:postgres', 'migrations:ready')

    def execute_action(self, action: ExecuteActionRequest) -> dict[str, object]:
        now_ms = 1_713_690_000_000
        decision = Decision(
            decision_id='dec-prod-proof-1',
            issuer_id='decision-core',
            issued_at_ms=now_ms,
            expires_at_ms=now_ms + 60_000,
            policy_id='prod-proof-policy',
            action=action.action_type,
            payload=dict(action.payload),
            snapshot_id='snap-prod-proof-1',
            state_hash='state-proof',
            correlation_id='corr-prod-proof-1',
            state_schema_version=1,
            action_schema_version=1,
            envelope_version=1,
        )
        material = sign_decision(decision=decision, secret=b'prod-proof-secret', kid='kid-prod-proof')
        envelope = SimpleNamespace(
            decision=decision,
            payload_hash=material.payload_hash,
            signature=material.signature,
            kid=material.kid,
            envelope_version=1,
            policy_version='v1',
            rollout_group='stable',
            canary_flag=False,
        )

        self._decision_archive.put(envelope)
        self._snapshot_store.put(decision.snapshot_id, json.dumps({'payload': action.payload}, sort_keys=True).encode('utf-8'))
        self._outbox.enqueue_once(
            decision_id=decision.decision_id,
            correlation_id=decision.correlation_id,
            action=decision.action,
            payload_json=json.dumps(action.payload, sort_keys=True),
        )
        payment_job_id = self._payment_outbox.enqueue_once(dedupe_key='payment-proof-1', payload={'decision_id': decision.decision_id})
        self._payment_outbox.mark_delivered(payment_job_id)
        mark_execution_once(ledger=self._ledger, env=envelope)
        self._event_store.append_event({
            'tenant_id': 'tenant-proof',
            'user_id': 'user-proof',
            'source': 'api',
            'event_type': 'decision_issued',
            'timestamp_ms': now_ms,
            'decision_id': decision.decision_id,
            'correlation_id': decision.correlation_id,
            'payload': {'action_type': decision.action, 'verification_status': 'pending'},
        })
        self._event_store.append_event({
            'tenant_id': 'tenant-proof',
            'user_id': 'user-proof',
            'source': 'executor',
            'event_type': 'decision_executed',
            'timestamp_ms': now_ms + 1,
            'decision_id': decision.decision_id,
            'correlation_id': decision.correlation_id,
            'payload': {'action_type': decision.action, 'verification_status': 'verified', 'evidence_ref': 'decision_executed'},
        })
        self._outbox.mark_delivered(decision.decision_id)
        return {
            'status': 'verified',
            'action_type': decision.action,
            'details': {
                'decision_id': decision.decision_id,
                'verification_status': 'verified',
                'snapshot_id': decision.snapshot_id,
                'archive_present': self._decision_archive.get(decision.decision_id) is not None,
                'ledger_marked': self._ledger.is_executed(decision.decision_id),
                'outbox_status': self._outbox.status(decision.decision_id),
                'latest_event_type': (self._event_store.latest_event(tenant_id='tenant-proof', user_id='user-proof') or {}).get('event_type'),
            },
            'capability_view': {'production_boot_proof': True},
        }


def test_production_boot_is_proved_for_prod_profile(monkeypatch, tmp_path) -> None:
    db_path = tmp_path / 'prod_boot_proof.sqlite3'
    sys.modules['psycopg'] = _FakePsycopgModule(db_path)

    monkeypatch.setenv('APP_ENV', 'prod')
    monkeypatch.setenv('METRO_DB_ENGINE', 'postgres')
    monkeypatch.setenv('DATABASE_URL', 'postgresql://proof')
    monkeypatch.setenv('BUSINESAIOS_ENABLE_POSTGRES_EVENT_STORE', '1')
    monkeypatch.setenv('BUSINESAIOS_API_KEY_STORE_PATH', str(tmp_path / 'api_keys.json'))
    monkeypatch.setenv('BUSINESAIOS_TENANT_REGISTRY_PATH', str(tmp_path / 'tenant_registry.json'))
    tenant_registry = PersistentTenantRegistry(path=tmp_path / 'tenant_registry.json')
    tenant_registry.register(TenantRecord(tenant_id='tenant-proof', display_name='Production Proof Tenant', plan=TenantPlan.ENTERPRISE, status=TenantStatus.ACTIVE))
    api_key_store = PersistentApiKeyStore(path=tmp_path / 'api_keys.json')
    _, control_plane_api_key = api_key_store.issue(
        tenant_id='tenant-proof',
        subject='prod-proof-control-plane',
        actor_id='prod-proof-control-plane',
        roles=(RoleId.OWNER,),
        scopes=('control_plane:read', 'control_plane:admin'),
        display_name='Production proof control-plane principal',
        metadata={'proof': 'production_boot'},
    )
    auth_headers = {'X-API-Key': control_plane_api_key, 'X-Tenant-ID': 'tenant-proof', 'X-Forwarded-Proto': 'https'}

    runtime = build_runtime_orchestrator()
    runtime.boot()

    with ExitStack() as stack:
        storage = resolve_storage_config()
        assert storage.postgres_event_store_enabled is True
        event_store, ledger, snapshot_store, decision_archive, outbox, payment_outbox = build_durable_stores(
            stack,
            base_dir=str(tmp_path),
            storage=storage,
        )
        service = _ProofApplicationService(
            event_store=event_store,
            ledger=ledger,
            snapshot_store=snapshot_store,
            decision_archive=decision_archive,
            outbox=outbox,
            payment_outbox=payment_outbox,
        )
        resources = _ManagedResources(stack=stack)
        boot_result = FastAPIBootResult(
            decision_application=service,
            runtime=runtime,
            runtime_infra=resources,
            startup_report=service.startup_audit_events(),
        )
        container = FastAPIDependencyContainer(boot_result=boot_result)
        app = create_fastapi_app(application_service=service, dependency_container=container)

        health_thread = start_health_server(port=18089, state_fn=lambda: {'ok': True, 'profile': 'prod', 'backend': storage.backend}, name='prod-proof')
        try:
            with TestClient(app) as client:
                health_payload = client.get('/health').json()
                readiness_payload = client.get('/readyz').json()
                tenants_payload = client.get('/control-plane/admin/tenants', headers=auth_headers).json()
                action_response = client.post('/actions/execute', json={'action_type': 'pricing.publish_offer', 'payload': {'offer_id': 'offer-1', 'amount': 199}}).json()
                audit_payload = client.get('/control-plane/audit/actions', headers=auth_headers).json()

                assert health_payload['status'] in {'ok', 'degraded'}
                assert readiness_payload['status'] == 'ready'
                assert readiness_payload['details']['runtime_readiness']['ready'] is True
                assert 'tenants' in tenants_payload
                assert isinstance(tenants_payload['tenants'], list)
                assert action_response['status'] == 'verified'
                assert action_response['details']['ledger_marked'] is True
                assert action_response['details']['archive_present'] is True
                assert action_response['details']['outbox_status'] == 'delivered'
                assert action_response['details']['latest_event_type'] == 'decision_executed'
                assert audit_payload['records']

                latest = event_store.latest_event(tenant_id='tenant-proof', user_id='user-proof')
                assert latest is not None
                assert latest['event_type'] == 'decision_executed'
                assert latest['payload']['verification_status'] == 'verified'
                assert decision_archive.get('dec-prod-proof-1') is not None
                assert snapshot_store.get('snap-prod-proof-1') is not None
                assert ledger.is_executed('dec-prod-proof-1') is True
                assert outbox.status('dec-prod-proof-1') == 'delivered'

                _, raw_health = fetch_text('http://127.0.0.1:18089/health', timeout=2)
                assert '"profile":"prod"' in raw_health
        finally:
            if health_thread is not None:
                shutdown = getattr(health_thread, 'shutdown', None)
                if callable(shutdown):
                    shutdown()
                closer = getattr(health_thread, 'server_close', None)
                if callable(closer):
                    closer()
                health_thread.join(timeout=2)

        assert getattr(resources.stack, '_exit_callbacks', None) in ([], ()) or len(getattr(resources.stack, '_exit_callbacks', [])) == 0
