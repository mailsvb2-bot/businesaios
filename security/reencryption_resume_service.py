from __future__ import annotations

from dataclasses import replace
from typing import Iterable

from security.key_management_contract import utc_now
from security.key_rotation_scheduler import SecretReencryptionAdapter
from security.reencryption_failure_policy import ReencryptionFailurePolicy
from security.reencryption_job_store import ReencryptionJob, SQLiteReencryptionJobStore
from security.reencryption_progress_ledger import ReencryptionProgressEvent, SQLiteReencryptionProgressLedger
from security.secret_vault_backend import SecretEnvelope, SecretVaultBackend


CANON_REENCRYPTION_RESUME_SERVICE = True


def _secret_ref_key(envelope: SecretEnvelope) -> str:
    return envelope.record.ref.key()


class ReencryptionResumeService:
    """Operational owner for resumable, batched secret reencryption.

    Uses the existing vault/key owner surfaces. No shadow secret state is introduced.
    """

    def __init__(
        self,
        *,
        job_store: SQLiteReencryptionJobStore,
        progress_ledger: SQLiteReencryptionProgressLedger,
        failure_policy: ReencryptionFailurePolicy,
        secret_backend: SecretVaultBackend,
        secret_reencryption_adapter: SecretReencryptionAdapter,
        key_provider,
    ) -> None:
        self._job_store = job_store
        self._ledger = progress_ledger
        self._failure_policy = failure_policy
        self._secret_backend = secret_backend
        self._adapter = secret_reencryption_adapter
        self._key_provider = key_provider

    def resume(self, *, job_id: str, batch_limit: int = 250) -> ReencryptionJob:
        job = self._job_store.get(job_id)
        active_job = replace(job, status='running')
        self._job_store.put(active_job)
        envelopes = self._secret_backend.list_by_encryption_key_id(
            encryption_key_id=active_job.old_key_id,
            tenant_id=active_job.tenant_id,
            connector_id=active_job.connector_id,
            limit=int(batch_limit),
        )
        if active_job.cursor_secret_ref:
            envelopes = tuple(env for env in envelopes if _secret_ref_key(env) > str(active_job.cursor_secret_ref))
        new_key = self._key_provider.get(active_job.new_key_id)
        processed = int(active_job.processed_count)
        failed = int(active_job.failed_count)
        consecutive_failures = 0
        cursor = active_job.cursor_secret_ref
        for envelope in envelopes:
            ref_key = _secret_ref_key(envelope)
            try:
                ciphertext = self._adapter.reencrypt_envelope(
                    envelope=envelope,
                    old_encryption_key_id=active_job.old_key_id,
                    new_key=new_key,
                )
                self._secret_backend.rekey(
                    ref=envelope.record.ref,
                    ciphertext=ciphertext,
                    encryption_key_id=new_key.key_id,
                    now=utc_now(),
                    expected_row_version=envelope.row_version,
                )
                processed += 1
                consecutive_failures = 0
                cursor = ref_key
                self._ledger.append(
                    ReencryptionProgressEvent(
                        job_id=active_job.job_id,
                        event_kind='secret_rekeyed',
                        secret_ref=ref_key,
                        ok=True,
                        payload={'new_key_id': new_key.key_id},
                    )
                )
            except Exception as exc:
                failed += 1
                consecutive_failures += 1
                self._ledger.append(
                    ReencryptionProgressEvent(
                        job_id=active_job.job_id,
                        event_kind='secret_rekey_failed',
                        secret_ref=ref_key,
                        ok=False,
                        payload={'error': exc.__class__.__name__, 'message': str(exc)},
                    )
                )
                decision = self._failure_policy.evaluate(
                    processed_count=processed,
                    failed_count=failed,
                    consecutive_failures=consecutive_failures,
                )
                if decision.action != 'continue':
                    paused = replace(active_job, status='paused', cursor_secret_ref=cursor, processed_count=processed, failed_count=failed)
                    self._job_store.put(paused)
                    self._ledger.append(
                        ReencryptionProgressEvent(
                            job_id=active_job.job_id,
                            event_kind='job_paused',
                            secret_ref=cursor,
                            ok=False,
                            payload={'reason': decision.reason},
                        )
                    )
                    return paused
        terminal_status = 'completed'
        if envelopes and len(envelopes) >= int(batch_limit):
            terminal_status = 'pending'
        updated = replace(active_job, status=terminal_status, cursor_secret_ref=cursor, processed_count=processed, failed_count=failed)
        self._job_store.put(updated)
        self._ledger.append(
            ReencryptionProgressEvent(
                job_id=active_job.job_id,
                event_kind='job_' + terminal_status,
                secret_ref=cursor,
                ok=terminal_status == 'completed',
                payload={'processed_count': processed, 'failed_count': failed},
            )
        )
        return updated


__all__ = [
    'CANON_REENCRYPTION_RESUME_SERVICE',
    'ReencryptionResumeService',
]
