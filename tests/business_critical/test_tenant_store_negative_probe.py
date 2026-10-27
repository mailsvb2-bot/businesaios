"""Empty-tenant probes must reject for tenant reasons, not arbitrary storage failures."""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from bootstrap import tenant_hard_gate as gate


class _Store:
    def __init__(self, failure):
        self.failure = failure

    def append_event(self, *, tenant_id, event_type, user_id, payload):
        raise self.failure

    def iter_events(self, *, tenant_id):
        return iter(())


def _log():
    return SimpleNamespace(emit=lambda *, tenant_id, event_type, user_id, payload, source: None)


@pytest.mark.parametrize(
    ("failure", "message"),
    [
        (OSError("database offline"), "failed unexpectedly: OSError"),
        (RuntimeError("storage corrupt"), "failed unexpectedly: RuntimeError"),
        (ValueError("invalid payload"), "rejected for unrelated reason"),
    ],
)
def test_empty_tenant_probe_does_not_mask_storage_failures(monkeypatch, failure, message):
    # The append probe fails before emission checks are reached.
    with pytest.raises(SystemExit, match=message):
        gate.validate_runtime_objects(tenant_id="real-tenant", event_store=_Store(failure), event_log=_log())


def test_explicit_empty_tenant_rejection_passes_to_emission_checks(monkeypatch):
    store = _Store(ValueError("tenant_id is required"))
    calls = []
    def reject(_event_log, *, tenant_id, event_type, payload):
        calls.append(tenant_id)
        if not tenant_id or tenant_id == "__other__":
            raise ValueError("tenant_id invalid")
    monkeypatch.setattr(gate, "_emit_probe", reject)
    gate.validate_runtime_objects(tenant_id="real-tenant", event_store=store, event_log=_log())
    assert calls == ["", "__other__", "real-tenant"]
