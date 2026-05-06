from __future__ import annotations

from core.ai.policy_registry import PolicyRegistry
from registry.base_registry import BaseRegistry
from registry.routing_policy_registry import RoutingPolicyRegistry


class _PolicyA:
    id = "policy-a"


class _PolicyB:
    id = "policy-b"


def test_base_registry_and_routing_registry_semantics_stay_stable() -> None:
    registry = BaseRegistry(kind="demo")
    registry.register("x", 1)
    registry.register("x", 2)
    assert registry.get("x") == 2

    unique = BaseRegistry(kind="demo")
    unique.register_unique("x", 1)
    try:
        unique.register_unique("x", 2)
    except ValueError as exc:
        assert str(exc) == "duplicate demo: x"
    else:
        raise AssertionError("duplicate register_unique must fail")

    snapshot = BaseRegistry(kind="demo")
    snapshot.register("b", 2)
    snapshot.register("a", 1)
    assert snapshot.snapshot() == {"b": 2, "a": 1}
    assert snapshot.items() == (("a", 1), ("b", 2))

    routing = RoutingPolicyRegistry()
    routing.register("p", object())
    try:
        routing.register("p", object())
    except ValueError as exc:
        assert str(exc) == "duplicate routing_policy: p"
    else:
        raise AssertionError("routing policy registry must reject duplicates")

def test_core_ai_policy_registry_semantics_stay_stable() -> None:
    registry = PolicyRegistry()
    assert registry._policies.__class__.__module__ == "core.ai._policy_registry_store"
    assert registry._policies.__class__.__name__ == "PolicyRegistryStore"

    first = _PolicyA()
    second = _PolicyA()
    registry.register(first)
    registry.register(second)
    assert registry.get("policy-a") is second
    assert registry.active() is second

    registry = PolicyRegistry()
    a = _PolicyA()
    b = _PolicyB()
    registry.register(a)
    registry.register(b)
    assert registry.maybe_get("policy-a") is a
    assert registry.maybe_get("missing") is None
    assert registry.registered_policy_ids() == ("policy-a", "policy-b")
