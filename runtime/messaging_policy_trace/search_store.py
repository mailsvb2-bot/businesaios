from __future__ import annotations

import importlib

from runtime.tenancy import normalize_tenant_scope


class MessagingPolicyTraceSearchStore:
    def __init__(self, *, event_store):
        self._event_store = event_store

    def search_records(self, *, tenant_id: str, user_id: str, date_from: str, date_to: str):
        tenant_scope = normalize_tenant_scope(tenant_id, allow_unknown=True)
        items = self._iter_all_records(tenant_id=tenant_scope)
        out = []
        for record in items:
            if str(record.tenant_id) != tenant_scope:
                continue
            if user_id and str(record.user_id) != str(user_id):
                continue
            if date_from and str(getattr(record, 'created_at', getattr(record, 'date', '')) or '') < str(date_from):
                continue
            if date_to and str(getattr(record, 'created_at', getattr(record, 'date', '')) or '') > str(date_to):
                continue
            out.append(record)
        return out

    def _iter_all_records(self, *, tenant_id: str):
        tenant_scope = normalize_tenant_scope(tenant_id, allow_unknown=True)
        if self._event_store is None:
            return []
        if not hasattr(self._event_store, 'iter_events'):
            return []
        call_iter_events = importlib.import_module("core.events.read_call").call_iter_events
        return list(
            call_iter_events(
                iter_fn=self._event_store.iter_events,
                tenant_id=tenant_scope,
                event_types=(),
                allow_zero_arg_fallback=True,
            )
        )
