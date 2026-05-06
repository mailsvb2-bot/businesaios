from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Tuple


def bellman_optimality(v_next: float, reward: float, gamma: float) -> float:
    """Bellman one-step: V = R + γ V(s')"""
    g = float(gamma)
    if g < 0 or g > 1:
        raise ValueError("gamma must be in [0,1].")
    return float(reward) + g * float(v_next)


@dataclass
class MDP:
    states: List[str]
    actions: List[str]
    transition: Dict[str, Dict[str, List[Tuple[str, float]]]]  # s,a -> [(s2,p)]
    reward: Dict[str, Dict[str, Dict[str, float]]]  # s,a,s2 -> r


def value_iteration(
    mdp: MDP,
    *,
    gamma: float = 0.95,
    iters: int = 200,
    tol: float = 1e-10,
) -> Tuple[Dict[str, float], Dict[str, str]]:
    """Classic value iteration for small MDPs."""
    g = float(gamma)
    if g < 0 or g > 1:
        raise ValueError("gamma must be in [0,1].")

    V: Dict[str, float] = {s: 0.0 for s in mdp.states}
    policy: Dict[str, str] = {s: mdp.actions[0] for s in mdp.states} if mdp.actions else {}

    for _ in range(iters):
        delta = 0.0
        newV: Dict[str, float] = {}
        for s in mdp.states:
            best_val = None
            best_a = None
            for a in mdp.actions:
                trans = mdp.transition.get(s, {}).get(a, [])
                q = 0.0
                for s2, p in trans:
                    r = mdp.reward.get(s, {}).get(a, {}).get(s2, 0.0)
                    q += float(p) * (float(r) + g * V.get(s2, 0.0))
                if best_val is None or q > best_val:
                    best_val = q
                    best_a = a
            v = float(best_val) if best_val is not None else 0.0
            newV[s] = v
            policy[s] = best_a if best_a is not None else policy.get(s, "")
            delta = max(delta, abs(newV[s] - V[s]))
        V = newV
        if delta <= tol:
            break
    return V, policy
