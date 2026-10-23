"""Executor-owned CRM identity projection (donor event_customer_projection effect side).

The only runtime path that writes canonical customers from a bot flow. ``customer_registry`` is the
canonical crm.CustomerRegistry injected at boot (needs EventStore + idempotency + PII vault); when it is
absent the effect is a no-op returning ``crm_unavailable`` — registration durability never depends on it.
"""

from __future__ import annotations

from typing import Any

from runtime.security.runtime_asserts import assert_called_from_executor

_CHANNELS = frozenset({"email", "phone"})


def build_bot_customer_registry(event_store: Any, idempotency_store: Any = None) -> Any:
    """Canonical CustomerRegistry over the bot's EventStore + its paired idempotency store + default PII vault.

    The idempotency store must live with the EventStore (claims point at facts): the executor's reliability
    store (shared with MessageRegistry) is reused; the API store path is only a fallback. No shadow customer store.
    """
    from bootstrap.bootstrap_config_surface import build_bootstrap_config_surface
    from crm.customer_registry import CustomerRegistry
    from reliability.idempotency_sqlite_backend import SQLiteIdempotencyStore
    from security.secret_vault import build_default_secret_vault

    if idempotency_store is None:
        path = build_bootstrap_config_surface().api_idempotency_path
        path.parent.mkdir(parents=True, exist_ok=True)
        idempotency_store = SQLiteIdempotencyStore(path)
    return CustomerRegistry(event_store=event_store, idempotency_store=idempotency_store,
                            pii_vault=build_default_secret_vault())


class CrmProjectionEffectsMixin:
    event_log: Any
    customer_registry: Any = None
    customer_registry_factory: Any = None

    def _crm_registry(self) -> Any:
        store = getattr(self, "event_store", None)
        if self.customer_registry is None and self.customer_registry_factory is None and store is not None:
            claims = getattr(getattr(getattr(self, "message_registry", None), "_writer", None), "_claims", None)
            self.customer_registry_factory = lambda: build_bot_customer_registry(store, claims)
        if self.customer_registry is None and callable(self.customer_registry_factory):
            factory, self.customer_registry_factory = self.customer_registry_factory, False
            try:
                self.customer_registry = factory()
            except Exception as exc:  # fail closed: registration stays durable, CRM reported unavailable
                self.event_log.emit(event_type="crm_registry_unavailable", source="crm", user_id="system",
                                    payload={"error": type(exc).__name__})
        return self.customer_registry

    def ensure_customer_identity(self, *, decision_id: str, correlation_id: str, tenant_id: str, business_id: str,
                                 channel: str, external_subject: str, display_name: str | None = None,
                                 customer_id: str | None = None) -> dict[str, Any]:
        """customer_id given -> attach identity to it (conflict -> ok False, no merge); else ensure by identity."""
        assert_called_from_executor()
        if channel not in _CHANNELS:
            raise ValueError("crm_channel_invalid")
        reg = self._crm_registry()
        if reg is None:
            return {"ok": False, "reason": "crm_unavailable"}
        from contracts.customer import CustomerIdentityConflict
        kw = {"tenant_id": tenant_id, "business_id": business_id, "channel": channel,
              "external_subject": external_subject, "display_name": display_name, "correlation_id": correlation_id}
        try:
            if customer_id:
                reg.attach_identity(customer_id=customer_id, **kw)
                cid = customer_id
            else:
                cid = reg.ensure_customer_identity(**kw).customer.customer_id
        except CustomerIdentityConflict:
            return {"ok": False, "reason": "identity_conflict"}
        self.event_log.emit(event_type="crm_identity_projected", source="crm", user_id=str(cid),
                            decision_id=str(decision_id), correlation_id=str(correlation_id),
                            payload={"tenant_id": tenant_id, "business_id": business_id, "channel": channel,
                                     "customer_id": cid})
        return {"ok": True, "customer_id": cid}


__all__ = ["CrmProjectionEffectsMixin", "build_bot_customer_registry"]
