from __future__ import annotations

"""Canonical representation package with compat alias submodules."""

class AuxiliaryTask:
    def score(self, prediction: float, target: float) -> float:
        return abs(prediction - target)

class ContrastiveObjective:
    def score(self, anchor: float, positive: float, negative: float) -> float:
        return abs(anchor - positive) - abs(anchor - negative)

class ImaginationRollouts:
    def rollout(self, state: dict, horizon: int) -> list[dict]:
        return [dict(state, imagined_step=step) for step in range(max(0, int(horizon)))]

class LatentDynamics:
    def transition(self, latent_state: dict, action_payload: dict) -> dict:
        updated = dict(latent_state)
        updated.update(action_payload)
        return updated

class LatentState:
    def __init__(self, values: dict) -> None:
        self.values = dict(values)

class ObservationEncoder:
    def encode(self, observation: dict) -> dict:
        return dict(observation)

class PredictiveRepresentation:
    def represent(self, latent_state: dict) -> dict:
        return dict(latent_state)

class SequenceEncoder:
    def encode(self, sequence) -> list:
        return list(sequence)

class StateAbstraction:
    def abstract(self, state: dict, keys) -> dict:
        return {key: state[key] for key in keys if key in state}

class StateEncoder:
    def encode(self, state: dict) -> dict:
        return dict(state)

class TemporalEncoder:
    def encode(self, timestep: int) -> dict:
        return {"timestep": int(timestep)}

class WorldModel:
    def predict(self, state: dict, action_payload: dict) -> dict:
        predicted = dict(state)
        predicted.update(action_payload)
        return predicted

__all__ = [
    "AuxiliaryTask",
    "ContrastiveObjective",
    "ImaginationRollouts",
    "LatentDynamics",
    "LatentState",
    "ObservationEncoder",
    "PredictiveRepresentation",
    "SequenceEncoder",
    "StateAbstraction",
    "StateEncoder",
    "TemporalEncoder",
    "WorldModel",
]
