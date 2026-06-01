from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from runtime.platform.support.contracts.observation import Observation


@dataclass(frozen=True)
class ActionRequestDTO:
    observation: Mapping[str, Any]

class ActionHandlerBundle:
    def __init__(self, service, response_builder) -> None:
        self._service = service
        self._response_builder = response_builder

    def handle(self, runtime, payload: dict) -> dict:
        observation = Observation(data=payload["observation"])
        action = self._service.act(runtime, observation)
        return self._response_builder.build(action)

class ActionHandler:
    def __init__(self, bundle: ActionHandlerBundle) -> None:
        self._bundle = bundle

    def handle(self, runtime, payload: dict) -> dict:
        return self._bundle.handle(runtime, payload)

class BatchActionHandler:
    def __init__(self, bundle: ActionHandlerBundle) -> None:
        self._bundle = bundle

    def handle(self, runtime, payloads: list[dict]) -> list[dict]:
        return [self._bundle.handle(runtime, payload) for payload in payloads]

class HealthHandler:
    def handle(self) -> dict[str, str]:
        return {"status": "ok"}

class MetricsHandler:
    def handle(self, metrics: dict) -> dict:
        return dict(metrics)

class Parser:
    def parse(self, payload: dict) -> dict:
        return dict(payload)

class ReadinessHandler:
    def handle(self) -> dict[str, str]:
        return {"ready": "true"}

class RequestValidation:
    def valid(self, payload: dict) -> bool:
        return "observation" in payload

class ResponseValidation:
    def valid(self, payload: dict) -> bool:
        return "action" in payload

class Serializer:
    def serialize(self, payload) -> dict:
        return dict(payload)

__all__ = [
    "ActionHandler",
    "ActionHandlerBundle",
    "ActionRequestDTO",
    "BatchActionHandler",
    "HealthHandler",
    "MetricsHandler",
    "Parser",
    "ReadinessHandler",
    "RequestValidation",
    "ResponseValidation",
    "Serializer",
]
