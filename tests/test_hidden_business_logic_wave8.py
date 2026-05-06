from __future__ import annotations

from config.economics_world_model_policy import DOWSeasonalityPolicy, PricingWorldModelPolicy
from config.experiments_policy import (
    ConservativeRolloutPolicyDefaults,
    ExperimentResultEvaluationPolicy,
    ExperimentResultExplanationPolicy,
)
from core.economics.world_model.seasonality import DOWSeasonalityModel
from core.economics.world_model.types import DemandObservation, MarketContext, PricePoint
from core.economics.world_model.world_model import PricingWorldModel
from core.experiments.enums import RiskLevel, RolloutDecision
from core.experiments.evaluators.experiment_result_evaluator import ExperimentResultEvaluator
from core.experiments.explainers.experiment_result_explainer import (
    ExperimentResultExplainer,
    explain_experiment_result,
)
from core.experiments.policies.rollout_policy import ConservativeRolloutPolicy
from core.experiments.types import (
    EvaluationSummary,
    ExperimentResult,
    VariantMetricSnapshot,
)


def test_conservative_rollout_policy_uses_zero_uplift_policy_floor() -> None:
    policy = ConservativeRolloutPolicy(
        ConservativeRolloutPolicyDefaults(zero_uplift_floor=-0.05)
    )
    decision = policy.evaluate(
        significant=True,
        uplift=-0.01,
        risk_level=RiskLevel.LOW,
    )
    assert decision == RolloutDecision.FULL


def test_experiment_result_evaluator_uses_policy_reason_strings() -> None:
    evaluator = ExperimentResultEvaluator(
        evaluation_policy=ExperimentResultEvaluationPolicy(
            zero_uplift_floor=0.1,
            control_below_minimum_reason='control low',
            treatment_below_minimum_reason='treatment low',
            negative_uplift_reason='uplift below floor',
            not_significant_reason='not significant',
        )
    )
    summary = evaluator.evaluate(
        experiment_id='exp-1',
        control_conversions=1,
        control_exposures=10,
        treatment_conversions=2,
        treatment_exposures=10,
        minimum_required_exposures=20,
    )
    assert 'control low' in summary.reasons
    assert 'treatment low' in summary.reasons
    assert 'not significant' in summary.reasons


def test_experiment_result_explainer_uses_policy_defaults() -> None:
    explainer = ExperimentResultExplainer(
        explanation_policy=ExperimentResultExplanationPolicy(
            no_blocking_reasons_text='none',
            confidence_ceiling=2.0,
            uplift_precision_digits=2,
        )
    )
    summary = EvaluationSummary(
        experiment_id='exp-1',
        significant=True,
        uplift=0.12345,
        p_value=0.25,
        risk_level=RiskLevel.LOW,
        rollout_decision=RolloutDecision.FULL,
        reasons=[],
    )
    text = explainer.explain(summary)
    assert 'uplift=0.12' in text
    assert 'reasons=none' in text
    result_text = explain_experiment_result(
        ExperimentResult(
            result_id='result-1',
            experiment_id='exp-1',
            primary_metric_key='signup_rate',
            control_variant_id='control',
            treatment_variant_id='treatment',
            control=VariantMetricSnapshot(variant_id='control', exposures=100, conversions=10),
            treatment=VariantMetricSnapshot(variant_id='treatment', exposures=100, conversions=12),
            uplift=0.2,
            p_value=0.25,
            significant=True,
            risk_level=RiskLevel.LOW,
            rollout_decision=RolloutDecision.FULL,
        ),
        explanation_policy=ExperimentResultExplanationPolicy(confidence_ceiling=2.0),
    )
    assert 'confidence=1.75' in result_text


def test_dow_seasonality_model_uses_policy_neutral_multiplier() -> None:
    model = DOWSeasonalityModel(mult={}, policy=DOWSeasonalityPolicy(neutral_multiplier=2.0))
    assert model.multiplier(dow=None) == 2.0
    assert model.multiplier(dow=4) == 2.0


def test_pricing_world_model_default_uses_policy_parameters() -> None:
    model = PricingWorldModel.default(
        policy=PricingWorldModelPolicy(
            zero_marginal_cost=0.0,
            default_demand_scale=3.0,
            default_demand_exponent=-2.0,
            default_conversion_bias=-3.0,
            default_conversion_slope=-0.02,
        )
    )
    assert model.demand.a == 3.0
    assert model.demand.b == -2.0
    assert model.conversion.w0 == -3.0
    assert model.conversion.w1 == -0.02


def test_dow_seasonality_calibrate_uses_policy_accumulators() -> None:
    ctx = MarketContext(tenant_id='t', product_id='p', currency='USD', dow=1)
    observations = [
        DemandObservation(context=ctx, price=PricePoint(10), units=5),
        DemandObservation(context=ctx, price=PricePoint(10), units=15),
    ]
    model = DOWSeasonalityModel.calibrate(
        observations,
        policy=DOWSeasonalityPolicy(
            neutral_multiplier=1.0,
            zero_accumulator=0.0,
            count_increment=2.0,
        ),
    )
    assert model.mult[1] == 1.0
