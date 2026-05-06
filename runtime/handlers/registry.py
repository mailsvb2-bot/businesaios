from __future__ import annotations
import importlib
from inspect import Parameter, signature
from typing import Any, Callable
from runtime.ports.effects import EffectsPort
class ActionHandlerRegistry:
    def __init__(self) -> None:
        self._handlers: dict[str, Callable[..., Any]] = {}
    def register(self, action: str, fn: Callable[..., Any]) -> None:
        self._handlers[str(action)] = fn
    def actions(self) -> set[str]:
        return set(self._handlers.keys()) | {"execute_plan@v1"}
    def dispatch(self, action: str, payload: dict, effects: EffectsPort, env: Any = None) -> Any:
        action_name = str(action)
        if action_name == 'execute_plan@v1':
            return self._dispatch_execute_plan(payload=payload, effects=effects, env=env)
        fn = self._handlers[action_name]
        accepts_keywords = importlib.import_module("core.utils.call_signature").accepts_keywords
        if accepts_keywords(fn, ("payload", "effects", "env")):
            return fn(payload=payload, effects=effects, env=env)
        try:
            params = tuple(signature(fn).parameters.values())
        except (TypeError, ValueError):
            params = ()
        positional = [p for p in params if p.kind in (Parameter.POSITIONAL_ONLY, Parameter.POSITIONAL_OR_KEYWORD)]
        if len(positional) >= 3:
            return fn(payload, effects, env)
        if len(positional) == 2:
            return fn(payload, effects)
        return fn(payload)
    def _dispatch_execute_plan(self, *, payload: dict, effects: EffectsPort, env: Any) -> list[Any]:
        steps = (payload or {}).get('steps')
        if not isinstance(steps, list):
            raise ValueError('execute_plan@v1 expects payload.steps as list')
        out=[]
        for step in steps:
            step_action = str(step.get('action'))
            if step_action == 'execute_plan@v1':
                raise ValueError('nested execute_plan@v1 is forbidden')
            step_payload = {k:v for k,v in step.items() if k not in {'action','action_schema_version'}}
            out.append(self.dispatch(step_action, step_payload, effects, env))
        return out
