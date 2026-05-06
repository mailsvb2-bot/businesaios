from __future__ import annotations

from security import SecretRecord, SecretRef, SecretSource, build_default_secret_vault
from .env_provider import EnvSecretProvider

_provider = EnvSecretProvider()
_vault = None
_DEFAULT_TENANT_ID = 'runtime'


def _get_vault():
    global _vault
    if _vault is None:
        _vault = build_default_secret_vault()
    return _vault


def _runtime_ref(key: str) -> SecretRef:
    return SecretRef(tenant_id=_DEFAULT_TENANT_ID, secret_name=str(key), version='current')


def register_runtime_secret(key: str, value: str, *, source: SecretSource = SecretSource.ENV) -> SecretRecord:
    """Registers a runtime secret in the canonical vault surface.

    This is an infrastructure adapter only. It does not create any policy or
    decision layer and preserves the historical env-first runtime behavior.
    """
    ref = _runtime_ref(key)
    return _get_vault().seed_plaintext(ref=ref, plaintext=value, source=source, metadata={'registered_by': 'infrastructure.secrets.runtime'})


def get_secret(key: str) -> str:
    """Single infra entrypoint for secrets.

    Core (Decision Ring) must not import this module.
    Historical behavior is preserved: environment remains the first source.
    The canonical vault is used as a safe cache/registration surface.
    """
    try:
        value = _provider.get(key)
    except RuntimeError:
        return _get_vault().get(_runtime_ref(key)).decode('utf-8')
    try:
        _get_vault().get_record(_runtime_ref(key))
    except KeyError:
        register_runtime_secret(key, value, source=SecretSource.ENV)
    return value
