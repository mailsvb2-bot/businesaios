"""Secret-reference resolution for external product connectors (secrets never enter facts or chat).

``env:NAME`` reads the process environment; ``vault:NAME`` reads the tenant SecretVault when one is
injected (``connector_id='external_product'``, scope = connector id). Unavailable -> ``None``.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from typing import Any

from security.secret_contract import SecretRef


def resolve_secret_ref(
    ref: str, *, tenant_id: str, connector_id: str, vault: Any | None = None, env: Mapping[str, str] | None = None,
    namespace: str = "external_product",
) -> str | None:
    kind, _, name = str(ref or "").partition(":")
    try:
        if kind == "env":
            value = (env if env is not None else os.environ).get(name)
            return None if value is None else str(value)
        if kind == "vault" and vault is not None:
            ref_ = SecretRef(tenant_id=tenant_id, secret_name=name, connector_id=namespace, scope=connector_id)
            return vault.get(ref_).decode("utf-8").strip()
    except Exception:  # noqa: BLE001 - never surface secret-adjacent errors
        return None
    return None


__all__ = ["resolve_secret_ref"]
