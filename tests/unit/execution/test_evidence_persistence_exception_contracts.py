from __future__ import annotations

import pytest

from execution.evidence_persistence_reliability import EvidencePersistenceReliabilitySupport


class _CheckpointStore:
    def latest(self, **_kwargs):
        raise OSError('checkpoint storage unavailable')

    def append(self, _checkpoint) -> None:
        raise AssertionError('append must not run after failed latest read')


class _LegacyReplayGuard:
    def is_replay(self, persistence_key: str) -> bool:
        return persistence_key == 'seen'


class _ModernReplayGuard:
    def __init__(self, error: Exception) -> None:
        self._error = error

    def is_replay(self, *, tenant_id: str, run_id: str, persistence_key: str) -> bool:
        del tenant_id, run_id, persistence_key
        raise self._error


def test_checkpoint_latest_failure_is_visible() -> None:
    support = EvidencePersistenceReliabilitySupport(checkpoint_store=_CheckpointStore())

    with pytest.raises(OSError, match='checkpoint storage unavailable'):
        support.checkpoint(
            tenant_id='tenant-1',
            run_id='run-1',
            stage='started',
            checkpoint_id='checkpoint-1',
            idempotency_key='key-1',
        )


def test_legacy_replay_guard_signature_remains_supported() -> None:
    support = EvidencePersistenceReliabilitySupport(replay_guard=_LegacyReplayGuard())

    assert support.replay_detected(tenant_id='tenant-1', run_id='run-1', persistence_key='seen') is True
    assert support.replay_detected(tenant_id='tenant-1', run_id='run-1', persistence_key='new') is False


def test_modern_replay_guard_internal_type_error_is_not_retried_as_legacy() -> None:
    support = EvidencePersistenceReliabilitySupport(
        replay_guard=_ModernReplayGuard(TypeError('replay backend bug')),
    )

    with pytest.raises(TypeError, match='replay backend bug'):
        support.replay_detected(tenant_id='tenant-1', run_id='run-1', persistence_key='key-1')


def test_modern_replay_guard_backend_failure_is_visible() -> None:
    support = EvidencePersistenceReliabilitySupport(
        replay_guard=_ModernReplayGuard(OSError('replay backend unavailable')),
    )

    with pytest.raises(OSError, match='replay backend unavailable'):
        support.replay_detected(tenant_id='tenant-1', run_id='run-1', persistence_key='key-1')
