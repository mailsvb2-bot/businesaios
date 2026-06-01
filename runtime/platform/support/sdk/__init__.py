from __future__ import annotations

from typing import Any

from .client import Client, TransportPort
from .dto import SDKRequest
from .errors import SDKError


class ActionClient(Client):
    def act(self, payload: dict[str, Any]) -> Any:
        return self.request("/action", payload)

class EvaluationClient(Client):
    def evaluate(self, payload: dict[str, Any]) -> Any:
        return self.request("/evaluate", payload)

class ExperimentClient(Client):
    def create_experiment(self, payload: dict[str, Any]) -> Any:
        return self.request("/experiments", payload)

class GovernanceClient(Client):
    def submit(self, payload: dict[str, Any]) -> Any:
        return self.request("/governance", payload)

class RolloutClient(Client):
    def start(self, payload: dict[str, Any]) -> Any:
        return self.request("/rollout", payload)

_ALIAS_EXPORTS = {
    "action_client": "ActionClient",
    "evaluation_client": "EvaluationClient",
    "experiment_client": "ExperimentClient",
    "governance_client": "GovernanceClient",
    "rollout_client": "RolloutClient",
}

__all__ = [
    "TransportPort",
    "Client",
    "SDKRequest",
    "SDKError",
    "ActionClient",
    "EvaluationClient",
    "ExperimentClient",
    "GovernanceClient",
    "RolloutClient",
]
