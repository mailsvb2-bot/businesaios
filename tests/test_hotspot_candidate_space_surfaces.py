from __future__ import annotations

from core.growth.ads.creative.bandit import CreativeArm, CreativeThompsonBandit
from core.scorers.bandit import EpsilonGreedyBandit, choose_bandit_arm, score_bandit_arms


def test_growth_optimizer_exposes_score_surface() -> None:
    out = score_bandit_arms(
        arms=("a", "b"),
        stats={"a": {"alpha": 2.0, "beta": 1.0}, "b": {"alpha": 1.0, "beta": 2.0}},
        seed="tenant-1",
    )
    assert len(out) == 2
    assert out[0].reason == "thompson_score_only"


def test_growth_optimizer_compat_choice_still_works() -> None:
    choice = choose_bandit_arm(
        arms=("a", "b"),
        stats={"a": {"alpha": 2.0, "beta": 1.0}, "b": {"alpha": 1.0, "beta": 2.0}},
        seed="tenant-1",
    )
    assert choice.key in {"a", "b"}


def test_creative_bandit_exposes_score_surface() -> None:
    bandit = CreativeThompsonBandit([CreativeArm("c1", "o1"), CreativeArm("c2", "o2")])
    out = bandit.score_all()
    assert len(out) == 2
    assert out[0].reason == "posterior_mean_score_only"


def test_canonical_bandit_class_stays_available() -> None:
    bandit = EpsilonGreedyBandit(epsilon=0.0, seed="tenant-1")
    bandit.update("a", 1.0)
    assert bandit.choose_arm(("a", "b")) == "a"
