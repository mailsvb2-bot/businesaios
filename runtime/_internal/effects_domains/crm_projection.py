"""Executor-owned CRM identity projection (donor event_customer_projection effect side).

The only runtime path that writes canonical customers from a bot flow. ``customer_registry`` is the
canonical crm.CustomerRegistry injected at boot (needs EventStore + idempotency + PII vault); when it is
absent the effect is a no-op returning ``crm_unavailable`` — registration durability never depends on it.
"""

from __future__ import annotations

from typing import Any

from runtime.security.runtime_asserts import assert_called_from_executor

_CHANNELS = frozenset({"email", "phone"})


class CrmProjectionEffectsMixin:
    event_log: Any
    customer_registry: Any = None

    def ensure_customer_identity(self, *, decision_id: str, correlation_id: str, tenant_id: str, business_id: str,
                                 channel: str, external_subject: str, display_name: str | None = None,
                                 customer_id: str | None = None) -> dict[str, Any]:
        """customer_id given -> attach identity to it (conflict -> ok False, no merge); else ensure by identity."""
        assert_called_from_executor()
        if channel not in _CHANNELS:
            raise ValueError("crm_channel_invalid")
        reg = self.customer_registry
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


__all__ = ["CrmProjectionEffectsMixin"]
