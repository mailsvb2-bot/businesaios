from __future__ import annotations

from application.business_autonomy.provider_catalog import provider_map
from runtime.business_autonomy.provider_live_sync_runtime import ProviderLiveSyncRuntime
from runtime.business_autonomy.provider_media import public_provider_media_payload
from runtime.business_autonomy.provider_queue_execution import ProviderQueueExecutionRuntime
from runtime.queue.job_contract import JobRecord, utc_now
from runtime.queue.job_store_sqlite import SqliteJobStore
from security.secret_contract import SecretRecord, SecretRef, SecretSource
from security.secret_vault import InMemorySecretVault


def _payload(source: str) -> dict:
    return {
        'user_id': '77',
        'text': 'listen',
        'attachments': [{'kind': 'voice', 'source': source}],
    }


def test_public_media_payload_never_exposes_local_source() -> None:
    source = '/srv/private/customers/secret-voice.ogg'
    public = public_provider_media_payload(_payload(source))
    assert source not in repr(public)
    attachment = public['attachments'][0]
    assert 'source' not in attachment
    assert len(attachment['source_ref_digest']) == 64


def test_provider_audit_and_request_envelope_redact_media_source() -> None:
    source = '/srv/private/customers/secret-voice.ogg'
    provider = provider_map()['max_messaging']
    vault = InMemorySecretVault()
    ref = SecretRef(
        tenant_id='tenant-a', connector_id=provider.connector_id, scope='business-a',
        secret_name=f'{provider.connector_id}.webhook_secret',
    )
    vault.put(
        SecretRecord(ref=ref, ciphertext=b'pending', source=SecretSource.CONNECTOR),
        plaintext=b'webhook-secret',
    )
    runtime = ProviderLiveSyncRuntime(vault, transports={})
    result = runtime.run(
        provider=provider,
        tenant_id='tenant-a',
        business_id='business-a',
        operation='message_send',
        mode='dry_run',
        payload=_payload(source),
    )
    assert source not in repr(result.metadata)
    audits = runtime.audit_recorder.audit_store.list_for_tenant(
        tenant_id='tenant-a', scope='provider_runtime'
    )
    assert audits and source not in repr(audits[0].payload)
    public = result.metadata['request_envelope']['payload']['attachments'][0]
    assert 'source' not in public
    assert len(public['source_ref_digest']) == 64


def test_provider_queue_control_plane_view_redacts_media_source(tmp_path) -> None:
    source = '/srv/private/customers/secret-voice.ogg'
    store = SqliteJobStore(tmp_path / 'provider-queue.sqlite3')
    now = utc_now()
    store.put(
        JobRecord(
            tenant_id='tenant-a',
            job_id='provider-sync-max-test',
            queue_name='provider_sync',
            job_type='provider_sync.dispatch',
            payload={
                'provider_key': 'max_messaging',
                'business_id': 'business-a',
                'operation': 'message_send',
                'mode': 'live',
                'payload': _payload(source),
            },
            dedupe_key='max-test',
            run_at=now,
        )
    )
    runtime = ProviderQueueExecutionRuntime(
        secret_vault=InMemorySecretVault(),
        live_runtime=ProviderLiveSyncRuntime(InMemorySecretVault(), transports={}),
        store=store,
    )
    rows = runtime.list_jobs(
        tenant_id='tenant-a', business_id='business-a', provider_key='max_messaging'
    )
    assert len(rows) == 1
    assert source not in repr(rows[0])
    attachment = rows[0]['payload']['payload']['attachments'][0]
    assert 'source' not in attachment
    assert len(attachment['source_ref_digest']) == 64
