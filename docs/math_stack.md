# Canonical Math Stack (core.math)

This package is **dependency-free** (stdlib only) and designed to be safe to import anywhere.

## What it is (and what it is not)

- It is a **toolbox** for scoring, calibration, ranking, exploration/exploitation, and analysis.
- It is **NOT** a second brain. It must not issue decisions directly.
- In this repo, **DecisionCore + Policy Gate + Soft Backoff** remain the only sources of executable constraints.

## Mapping to the 15 pillars

1) Bayes / probabilities -> `probability.py`  
2) Optimization + gradient descent -> `optimization.py`  
3) Bandits (UCB1 / Thompson) -> `bandits.py`  
4) Network effects (Metcalfe) -> `network.py`  
5) Graph theory (walk/similarity/co-occurrence reco) -> `graphs.py`  
6) PageRank -> `pagerank.py`  
7) Information theory (entropy) -> `information.py`  
8) Economics (LTV/CAC/unit profit) -> `economics.py`  
9) Queueing (Little/M/M/1) -> `queueing.py`  
10) Markov processes -> `markov.py`  
11) Complex systems (feedback loops) -> `complex_systems.py`  
12) Optimal control / RL (Bellman/value iteration) -> `control.py`  
13) A/B stats (z-test) -> `abtest.py`  
14) Power laws -> `powerlaw.py`  
15) Logistic function -> `logistic.py`

## Integration rule

All selectors (bandits/RL/scorers) must operate on:

- **allowed action set** (policy gate + soft-backoff masking),
- then choose argmax within that set.

Never "override" guardrails with probability.
