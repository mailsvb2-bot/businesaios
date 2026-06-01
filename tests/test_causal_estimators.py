from __future__ import annotations

from core.causal.api import estimate_causal_effect
from core.causal.types import CausalDataset, CausalQuery, CausalRow


def _mk_ds():
    rows = []
    # Two strata A/B; treatment is correlated with stratum.
    # True effect is +2.0 in both strata.
    for i in range(50):
        rows.append(CausalRow(unit_id=f"a_t{i}", timestamp_ms=1, treatment=1.0, outcome=10.0 +2.0, covariates={"s": "A"}))
    for i in range(10):
        rows.append(CausalRow(unit_id=f"a_c{i}", timestamp_ms=1, treatment=0.0, outcome=10.0, covariates={"s": "A"}))

    for i in range(10):
        rows.append(CausalRow(unit_id=f"b_t{i}", timestamp_ms=1, treatment=1.0, outcome=4.0 +2.0, covariates={"s": "B"}))
    for i in range(50):
        rows.append(CausalRow(unit_id=f"b_c{i}", timestamp_ms=1, treatment=0.0, outcome=4.0, covariates={"s": "B"}))

    return CausalDataset(rows=rows)


def test_diff_in_means_runs():
    ds = _mk_ds()
    q = CausalQuery(treatment_name="T", outcome_name="Y", method="diff_in_means")
    res = estimate_causal_effect(ds, query=q, bootstrap=False)
    assert isinstance(res.estimate.effect, float)


def test_stratified_recovers_effect():
    ds = _mk_ds()
    q = CausalQuery(treatment_name="T", outcome_name="Y", covariate_names=("s",), method="stratified")
    res = estimate_causal_effect(ds, query=q, bootstrap=False)
    assert abs(res.estimate.effect - 2.0) < 1e-6


def test_ipw_recovers_effect():
    ds = _mk_ds()
    q = CausalQuery(treatment_name="T", outcome_name="Y", covariate_names=("s",), method="ipw")
    res = estimate_causal_effect(ds, query=q, bootstrap=False)
    assert abs(res.estimate.effect - 2.0) < 1e-6


def test_dr_recovers_effect():
    ds = _mk_ds()
    q = CausalQuery(treatment_name="T", outcome_name="Y", covariate_names=("s",), method="dr")
    res = estimate_causal_effect(ds, query=q, bootstrap=False)
    assert abs(res.estimate.effect - 2.0) < 1e-6


def test_bootstrap_adds_ci():
    ds = _mk_ds()
    q = CausalQuery(treatment_name="T", outcome_name="Y", covariate_names=("s",), method="dr")
    res = estimate_causal_effect(ds, query=q, bootstrap=True, bootstrap_n=120, bootstrap_seed=7)
    assert res.estimate.stderr is not None
    assert res.estimate.ci95_low is not None
    assert res.estimate.ci95_high is not None
    assert res.estimate.ci95_low <= res.estimate.effect <= res.estimate.ci95_high


def test_diff_in_diff():
    rows = []
    # treated group increases by +3 post; control increases by +1 post => DiD effect +2
    for i in range(40):
        rows.append(CausalRow(unit_id=f"t{i}", timestamp_ms=1, treatment=1.0, outcome=5.0, covariates={"period": "pre"}))
        rows.append(CausalRow(unit_id=f"t{i}", timestamp_ms=2, treatment=1.0, outcome=8.0, covariates={"period": "post"}))
    for i in range(40):
        rows.append(CausalRow(unit_id=f"c{i}", timestamp_ms=1, treatment=0.0, outcome=5.0, covariates={"period": "pre"}))
        rows.append(CausalRow(unit_id=f"c{i}", timestamp_ms=2, treatment=0.0, outcome=6.0, covariates={"period": "post"}))

    ds = CausalDataset(rows=rows)
    q = CausalQuery(treatment_name="T", outcome_name="Y", method="did")
    res = estimate_causal_effect(ds, query=q, bootstrap=False)
    assert abs(res.estimate.effect - 2.0) < 1e-6
