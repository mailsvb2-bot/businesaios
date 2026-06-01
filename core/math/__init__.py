"""
core.math
---------
Canonical lightweight math stack for product decisioning:
- Probability / Bayes
- Optimization (loss, gradient descent)
- Bandits (UCB1, Thompson sampling)
- Network theory (Metcalfe)
- Graphs & PageRank
- Information theory (entropy)
- Economics (LTV/CAC)
- Queueing (Little's Law, M/M/1)
- Markov processes
- Complex systems (feedback loops)
- Optimal control / RL (Bellman, value iteration)
- A/B test stats (z-test)
- Power laws (Pareto, alpha MLE)
- Logistic function (sigmoid)
"""

from .abtest import z_test_proportions, z_to_pvalue_2sided
from .bandits import UCB1, ThompsonBernoulli
from .complex_systems import feedback_step, growth_step
from .control import MDP, bellman_optimality, value_iteration
from .economics import cac, ltv, unit_profit
from .graphs import (
    cooccurrence_recommendations,
    cosine_similarity,
    jaccard_similarity,
    random_walk,
)
from .information import entropy
from .logistic import logit, sigmoid
from .markov import (
    estimate_transition_counts,
    next_state_distribution,
    normalize_transition_counts,
)
from .network import metcalfe_value
from .optimization import gradient_descent, mse_loss
from .pagerank import pagerank
from .powerlaw import fit_alpha_mle, pareto_top_share
from .probability import HistorySignals, bayes, naive_bayes_posterior, purchase_prob_from_history
from .queueing import little_law, mm1_wait_time

__all__ = [
    "bayes",
    "naive_bayes_posterior",
    "HistorySignals",
    "purchase_prob_from_history",
    "mse_loss",
    "gradient_descent",
    "UCB1",
    "ThompsonBernoulli",
    "metcalfe_value",
    "cosine_similarity",
    "jaccard_similarity",
    "random_walk",
    "cooccurrence_recommendations",
    "pagerank",
    "entropy",
    "ltv",
    "cac",
    "unit_profit",
    "little_law",
    "mm1_wait_time",
    "estimate_transition_counts",
    "normalize_transition_counts",
    "next_state_distribution",
    "growth_step",
    "feedback_step",
    "bellman_optimality",
    "MDP",
    "value_iteration",
    "z_test_proportions",
    "z_to_pvalue_2sided",
    "pareto_top_share",
    "fit_alpha_mle",
    "sigmoid",
    "logit",
]
