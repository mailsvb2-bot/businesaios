"""Managed-bot token sealing (port of donor ManagedBotCredentialStore).

The raw token goes straight into the tenant SecretVault; callers and facts only ever see the
``vault:managed_bot.<external_bot_id>`` reference. ``discard`` is the rollback for a failed
activation. Resolution reuses ``resolve_secret_ref`` (``env:`` refs keep working).
"""

from __future__ import annotations

import re
from typing import Any

from runtime.integration.external_product_secrets import resolve_secret_ref
from security.secret_contract import SecretRecord, SecretRef, SecretSource

NAMESPACE = "managed_bot"
SCOPE = "telegram"
_BOT_ID = re.compile(r"[1-9][0-9]{0,19}")


def _ref(tenant_id: str, name: str) -> SecretRef:
    return SecretRef(tenant_id=tenant_id, secret_name=name, connector_id=NAMESPACE, scope=SCOPE)


def seal(vault: Any, *, tenant_id: str, external_bot_id: str, token: str) -> str:
    if vault is None:
        raise ValueError("managed_bot_vault_unavailable")
    if not _BOT_ID.fullmatch(str(external_bot_id)):
        raise ValueError("managed_bot_external_id_invalid")
    raw = str(token or "").strip()
    if not raw:
        raise ValueError("managed bot token is unavailable")
    name = f"{NAMESPACE}.{external_bot_id}"
    vault.put(
        SecretRecord(ref=_ref(tenant_id, name), ciphertext=b"pending", source=SecretSource.CONNECTOR),
        plaintext=raw.encode(),
    )
    return f"vault:{name}"


def resolve(ref: str, *, tenant_id: str, vault: Any | None = None) -> str | None:
    return resolve_secret_ref(ref, tenant_id=tenant_id, connector_id=SCOPE, vault=vault, namespace=NAMESPACE)


def discard(vault: Any, ref: str, *, tenant_id: str) -> bool:
    """Rollback: deactivate a sealed token; never raises, never reveals the value."""
    kind, _, name = str(ref or "").partition(":")
    if kind != "vault" or vault is None:
        return False
    try:
        vault.delete(_ref(tenant_id, name))
        return True
    except Exception:  # noqa: BLE001 - secret-adjacent errors stay silent
        return False


__all__ = ["NAMESPACE", "discard", "resolve", "seal"]
