from __future__ import annotations

from core.admin.read_models.common_support import supports_kwarg
from runtime.boot.tenant_hard_gate import _has_param
from runtime.handlers.registry import ActionHandlerRegistry


def _triple(payload, effects, env):
    return payload, effects, env


def _double(payload, effects):
    return payload, effects


def test_supports_kwarg_uses_canonical_signature_rules() -> None:
    assert supports_kwarg(_triple, "env") is True
    assert _has_param(_double, "env") is False


def test_action_handler_registry_dispatches_env_only_when_supported() -> None:
    reg = ActionHandlerRegistry()
    reg.register("triple", _triple)
    reg.register("double", _double)
    assert reg.dispatch("triple", {"x": 1}, object(), env="e")[2] == "e"
    assert len(reg.dispatch("double", {"x": 1}, object(), env="e")) == 2
