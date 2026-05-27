import math

from core.math import (
    UCB1,
    HistorySignals,
    ThompsonBernoulli,
    bayes,
    cac,
    entropy,
    fit_alpha_mle,
    little_law,
    logit,
    ltv,
    mm1_wait_time,
    pagerank,
    pareto_top_share,
    purchase_prob_from_history,
    sigmoid,
    unit_profit,
    z_test_proportions,
    z_to_pvalue_2sided,
)


def test_bayes_basic():
    # P(A)=0.01, P(B|A)=0.9, P(B)=0.05 => P(A|B)=0.18
    p = bayes(0.9, 0.01, 0.05)
    assert abs(p - 0.18) < 1e-9


def test_entropy_coin():
    # fair coin => 1 bit
    h = entropy([0.5, 0.5], base=2.0)
    assert abs(h - 1.0) < 1e-9


def test_sigmoid_logit_inverse():
    for x in [-5, -1, 0, 1, 5]:
        p = sigmoid(x)
        x2 = logit(p)
        assert abs(x - x2) < 1e-9


def test_economics():
    assert ltv(10, 3) == 30
    assert cac(100, 20) == 5
    assert unit_profit(arpu=10, lifetime=3, marketing_spend=100, users_acquired=20) == 25


def test_queueing():
    assert little_law(10, 2) == 5
    assert mm1_wait_time(1, 2) == 1.0
    assert math.isinf(mm1_wait_time(2, 2))


def test_pagerank_sums_to_one():
    g = {"A": ["B"], "B": ["A", "C"], "C": ["A"]}
    pr = pagerank(g, iters=200)
    s = sum(pr.values())
    assert abs(s - 1.0) < 1e-6


def test_bandits_smoke():
    u = UCB1(["a", "b"])
    a1 = u.select()
    u.update(a1, 1.0)
    a2 = u.select()
    u.update(a2, 0.0)

    t = ThompsonBernoulli(["x", "y"])
    ax = t.select()
    t.update(ax, 1)


def test_abtest_smoke():
    z = z_test_proportions(x1=120, n1=1000, x2=100, n2=1000)
    p = z_to_pvalue_2sided(z)
    assert 0.0 <= p <= 1.0


def test_powerlaw_helpers():
    xs = [100, 50, 25, 10, 5, 1]
    share = pareto_top_share(xs, 0.33)
    assert share > 0.5
    alpha = fit_alpha_mle([1, 2, 3, 4, 5], xmin=1.0)
    assert alpha > 1.0


def test_purchase_prob_baseline():
    h = HistorySignals(sessions_7d=3, content_completed_7d=1, paywall_opened_7d=0, offer_clicked_7d=0)
    p = purchase_prob_from_history(h, base_rate=0.02)
    assert 0.0 <= p <= 1.0
    assert p >= 0.02
