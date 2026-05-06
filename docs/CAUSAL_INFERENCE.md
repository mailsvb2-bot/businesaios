# Causal Inference (core.causal)

This project contains a **small, dependency-free causal inference toolkit** designed for production guardrails:

- Pure-core primitives (no provider/network imports)
- Deterministic-by-default
- No "god objects": small modules with explicit inputs/outputs

## What it is for

Typical product questions:

- *Did raising the price increase revenue (net of selection changes)?*
- *Did an ads plan apply actually increase conversions?*
- *Which segments benefit from a change?* (limited CATE via stratification)

## Concepts

- **Treatment**: what you changed (binary 0/1 for now)
- **Outcome**: what you care about (revenue, conversions, retention proxy)
- **Covariates**: confounders you want to adjust for (country, channel, plan, etc.)
- **Estimand**: ATE/ATT/CATE (we implement ATE as first-class)

## Included estimators

- `diff_in_means` — naive difference in means (baseline)
- `stratified` — exact adjustment by strata on covariates
- `ipw` — inverse propensity weighting with stratified propensity
- `dr` — doubly-robust (AIPW): stratified propensity + OLS outcome regression
- `did` — difference-in-differences for pre/post & treated/control

All estimators are implemented without numpy to keep the runtime minimal.

## How to use (pure)

```python
from core.causal.types import CausalDataset, CausalRow, CausalQuery
from core.causal.api import estimate_causal_effect

ds = CausalDataset(rows=[
    CausalRow(unit_id="u1", timestamp_ms=1, treatment=1, outcome=10.0, covariates={"country": "NL"}),
    CausalRow(unit_id="u2", timestamp_ms=1, treatment=0, outcome=7.0, covariates={"country": "NL"}),
])

q = CausalQuery(
    treatment_name="treated",
    outcome_name="revenue",
    covariate_names=("country",),
    method="dr",
)

res = estimate_causal_effect(ds, query=q)
print(res.estimate.effect, res.estimate.ci95_low, res.estimate.ci95_high)
```

## How to use (from EventStore)

See `core.causal.builders.event_store_builder.EventCausalBuilder`.

Example: estimate effect of `ads_plan_applied` on `payment_captured` amount.

```python
from core.causal.builders.event_store_builder import EventCausalBuilder
from core.causal.types import CausalQuery
from core.causal.api import estimate_causal_effect

builder = EventCausalBuilder(unit_id_key="user_id")
ds = builder.build_binary_treatment_dataset(
    event_store,
    tenant_id=tenant_id,
    treatment_event="ads_plan_applied",
    outcome_event="payment_captured",
    outcome_value_path=("payload", "amount"),
    covariate_extractors=(("platform", ("payload", "platform")),),
)

q = CausalQuery(treatment_name="ads_plan_applied", outcome_name="payment_amount", covariate_names=("platform",))
res = estimate_causal_effect(ds, query=q)
```

## Safety stance

- These estimators can **still be wrong** if the data is confounded, sparse, or nonstationary.
- Use as a decision-support signal, not as an autonomous actuator input without additional guardrails.
- Prefer explicit experiments whenever possible.
