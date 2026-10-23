from types import SimpleNamespace

from runtime._internal.effects_domains import crm_projection as cp


class _Fx(cp.CrmProjectionEffectsMixin):
    def __init__(self, store, claims=None):
        self.event_store = store
        self.customer_registry = None
        self.message_registry = SimpleNamespace(_writer=SimpleNamespace(_claims=claims))
        self.emitted = []
        self.event_log = self

    def emit(self, **k):
        self.emitted.append(k)


def test_lazy_factory_reuses_event_store_paired_claims(monkeypatch):
    seen = []
    monkeypatch.setattr(cp, "build_bot_customer_registry", lambda s, c: seen.append((s, c)) or "REG")
    fx = _Fx("STORE", "CLAIMS")
    assert fx._crm_registry() == "REG"
    assert fx._crm_registry() == "REG"
    assert seen == [("STORE", "CLAIMS")]


def test_lazy_factory_failure_is_attempted_once(monkeypatch):
    calls = []

    def boom(s, c):
        calls.append(1)
        raise RuntimeError("x")

    monkeypatch.setattr(cp, "build_bot_customer_registry", boom)
    fx = _Fx("STORE")
    assert fx._crm_registry() is None
    assert fx._crm_registry() is None
    assert calls == [1]
    assert fx.emitted[0]["event_type"] == "crm_registry_unavailable"


def test_no_event_store_no_registry():
    assert _Fx(None)._crm_registry() is None
