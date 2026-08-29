from contracts.event_store import AppendEvent as CanonicalAppendEvent
from contracts.event_store import normalize_append_event as canonical_normalize_append_event
from runtime.platform.config.registry import CONFIG
from runtime.platform.event_store.append_contract import AppendEvent, normalize_append_event


def test_config_registry_exposes_yaml_and_tenant_env_helpers(tmp_path):
    p = tmp_path / "sample.yaml"
    p.write_text("foo: 1\nbar: baz\n", encoding="utf-8")
    raw = CONFIG.yaml_from_path(p)
    assert raw["foo"] == 1
    assert CONFIG.tenant_env() is not None


def test_append_contract_runtime_path_is_compatibility_only():
    assert AppendEvent is CanonicalAppendEvent
    assert normalize_append_event is canonical_normalize_append_event


def test_append_contract_normalizes_aliases():
    ev = normalize_append_event({
        "tenant_id": "t1",
        "type": "x",
        "decision": "d1",
        "trace_id": "c1",
        "payload": {"ok": True},
        "source": "  ",
    })
    assert ev.source == "system"
    assert ev.decision_id == "d1"
    assert ev.correlation_id == "c1"
