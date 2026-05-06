from __future__ import annotations

import base64
import hashlib
import hmac
from dataclasses import dataclass

from runtime.platform.config.env_flags import env_bool, env_str
from security.key_management_contract import KeyMaterialRecord, KeyPurpose
from security.key_provider import InMemoryKeyProvider

"""Minimal HMAC signing for sandboxed execution.

This module preserves the historical bytes-in/bytes-out API while binding it
onto the canonical security key contract. It remains a transport primitive only
and must not become a decision surface.
"""


_KEY_PROVIDER = InMemoryKeyProvider()
_RUNTIME_SIGNING_KEY_ID = 'runtime-decision-signing-env'


def _load_secret() -> bytes:
    b64 = env_str('DECISIONCORE_SECRET_B64', '')
    if b64:
        return base64.b64decode(b64.encode('utf-8'))

    plain = env_str('DECISIONCORE_SECRET', '')

    env = env_str('ENV', env_str('APP_ENV', 'dev')).lower().strip()
    non_dev_envs = {'prod', 'production', 'stage', 'staging', 'preprod', 'qa'}
    if env in non_dev_envs and not plain.strip():
        raise RuntimeError(f'DECISIONCORE_SECRET must be set in {env} environment')

    if not plain:
        if env_bool('DECISIONCORE_SECRET_ALLOW_DEV_DEFAULT', False):
            plain = 'dev-decisioncore-secret'
        else:
            raise RuntimeError(
                'DECISIONCORE_SECRET not set. '
                'Set DECISIONCORE_SECRET_ALLOW_DEV_DEFAULT=1 for local dev, '
                'or provide a real secret.'
            )
    return plain.encode('utf-8')


def _resolve_runtime_key() -> KeyMaterialRecord:
    secret = _load_secret()
    try:
        current = _KEY_PROVIDER.get(_RUNTIME_SIGNING_KEY_ID)
    except KeyError:
        current = KeyMaterialRecord(
            key_id=_RUNTIME_SIGNING_KEY_ID,
            purpose=KeyPurpose.REQUEST_SIGNING,
            secret_bytes=secret,
            tenant_id='runtime',
        )
        current.validate()
        _KEY_PROVIDER.register(current)
        return current
    if current.secret_bytes != secret:
        updated = KeyMaterialRecord(
            key_id=_RUNTIME_SIGNING_KEY_ID,
            purpose=KeyPurpose.REQUEST_SIGNING,
            secret_bytes=secret,
            tenant_id='runtime',
        )
        updated.validate()
        _KEY_PROVIDER.register(updated)
        return updated
    return current


@dataclass(frozen=True)
class SignedDecision:
    payload: bytes
    signature: bytes


def sign(payload: bytes) -> SignedDecision:
    key = _resolve_runtime_key()
    sig = hmac.new(key.secret_bytes, payload, hashlib.sha256).digest()
    return SignedDecision(payload, sig)


def verify(decision: SignedDecision) -> None:
    key = _resolve_runtime_key()
    expected = hmac.new(key.secret_bytes, decision.payload, hashlib.sha256).digest()
    if not hmac.compare_digest(expected, decision.signature):
        raise RuntimeError('INVALID_DECISION_SIGNATURE')
