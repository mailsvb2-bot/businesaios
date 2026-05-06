from __future__ import annotations

from security.encryption_policy import EncryptionAlgorithm, EncryptionPolicy
from security.key_management_contract import KeyPurpose
from security.key_provider import InMemoryKeyProvider
from security.key_rotation_scheduler import StdlibSecretReencryptionAdapter
from security.reencryption_failure_policy import ReencryptionFailurePolicy
from security.reencryption_job_store import ReencryptionJob, SQLiteReencryptionJobStore
from security.reencryption_progress_ledger import SQLiteReencryptionProgressLedger
from security.reencryption_resume_service import ReencryptionResumeService
from security.secret_contract import SecretRef
from security.secret_vault import decrypt_secret_payload, encrypt_secret_payload
from security.secret_vault_sqlite import SqliteSecretVaultBackend


def test_reencryption_resume_service_rekeys_bound_secret_and_marks_job_complete(tmp_path) -> None:
    policy = EncryptionPolicy(algorithm=EncryptionAlgorithm.SEALED_BOX_V1)
    key_provider = InMemoryKeyProvider()
    old_key = key_provider.issue_key(key_id='old-key', purpose=KeyPurpose.SECRET_ENCRYPTION, tenant_id='t1')
    new_key = key_provider.issue_key(key_id='new-key', purpose=KeyPurpose.SECRET_ENCRYPTION, tenant_id='t1')
    backend = SqliteSecretVaultBackend(tmp_path / 'vault.sqlite3')
    ref = SecretRef(tenant_id='t1', secret_name='db_password', version='v1')
    ciphertext = encrypt_secret_payload(
        plaintext=b'super-secret',
        ref=ref,
        encryption_key_id=old_key.key_id,
        key_provider=key_provider,
        policy=policy,
        sealed_box_magic=b'SB1:',
    )
    backend.seed_encrypted(ref=ref, ciphertext=ciphertext, encryption_key_id=old_key.key_id)

    job_store = SQLiteReencryptionJobStore(str(tmp_path / 'jobs.sqlite3'))
    job_store.put(ReencryptionJob(job_id='job-1', old_key_id=old_key.key_id, new_key_id=new_key.key_id, tenant_id='t1'))
    ledger = SQLiteReencryptionProgressLedger(str(tmp_path / 'progress.sqlite3'))
    service = ReencryptionResumeService(
        job_store=job_store,
        progress_ledger=ledger,
        failure_policy=ReencryptionFailurePolicy(),
        secret_backend=backend,
        secret_reencryption_adapter=StdlibSecretReencryptionAdapter(key_provider=key_provider, policy=policy),
        key_provider=key_provider,
    )

    result = service.resume(job_id='job-1')
    updated = backend.get(ref)
    plaintext = decrypt_secret_payload(
        ciphertext=updated.record.ciphertext,
        ref=ref,
        encryption_key_id=new_key.key_id,
        key_provider=key_provider,
        policy=policy,
        sealed_box_magic=b'SB1:',
    )

    assert result.status == 'completed'
    assert result.processed_count == 1
    assert updated.encryption_key_id == new_key.key_id
    assert plaintext == b'super-secret'
    assert any(event.event_kind == 'secret_rekeyed' for event in ledger.latest_for_job('job-1'))
