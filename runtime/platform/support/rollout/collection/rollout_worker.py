from __future__ import annotations

from runtime.platform.support.contracts.action import Action
from runtime.platform.support.contracts.trajectory import Trajectory
from runtime.platform.support.contracts.transition import Transition


class RolloutWorker:
    def __init__(self, env, policy, max_steps: int) -> None:
        self._env = env
        self._policy = policy
        self._max_steps = max_steps

    def collect(self, _request=None) -> Trajectory:
        observation = self._env.reset()
        transitions: list[Transition] = []

        for _ in range(self._max_steps):
            action = self._policy.act(observation)
            next_observation, reward, done = self._env.step(action if isinstance(action, Action) else Action(name="raw", payload=action))
            transitions.append(
                Transition(
                    observation=observation,
                    action=action if isinstance(action, Action) else Action(name="raw", payload=action),
                    reward=reward,
                    done=done,
                )
            )
            observation = next_observation
            if done:
                break

        return Trajectory(transitions=transitions)

__all__ = [
    "RolloutWorker",
]
