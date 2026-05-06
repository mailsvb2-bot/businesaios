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

from .probability import bayes, naive_bayes_posterior, purchase_prob_from_history, HistorySignals
from .optimization import mse_loss, gradient_descent
from .bandits import UCB1, ThompsonBernoulli
from .network import metcalfe_value
from .graphs import (
    cosine_similarity,
    jaccard_similarity,
    random_walk,
    cooccurrence_recommendations,
)
from .pagerank import pagerank
from .information import entropy
from .economics import ltv, cac, unit_profit
from .queueing import little_law, mm1_wait_time
from .markov import (
    estimate_transition_counts,
    normalize_transition_counts,
    next_state_distribution,
)
from .complex_systems import growth_step, feedback_step
from .control import bellman_optimality, value_iteration, MDP
from .abtest import z_test_proportions, z_to_pvalue_2sided
from .powerlaw import pareto_top_share, fit_alpha_mle
from .logistic import sigmoid, logit

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
