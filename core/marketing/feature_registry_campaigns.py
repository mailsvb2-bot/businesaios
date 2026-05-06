from __future__ import annotations
from core.marketing.feature_registry_shared import FeatureSpec

FEATURES = [
    FeatureSpec(name='offer_shown_1d', dtype='float', group='offer_funnel', desc='offer_funnel:offer_shown_1d'),
    FeatureSpec(name='offer_shown_7d', dtype='float', group='offer_funnel', desc='offer_funnel:offer_shown_7d'),
    FeatureSpec(name='offer_shown_30d', dtype='float', group='offer_funnel', desc='offer_funnel:offer_shown_30d'),
    FeatureSpec(name='offer_clicked_1d', dtype='float', group='offer_funnel', desc='offer_funnel:offer_clicked_1d'),
    FeatureSpec(name='offer_clicked_7d', dtype='float', group='offer_funnel', desc='offer_funnel:offer_clicked_7d'),
    FeatureSpec(name='offer_clicked_30d', dtype='float', group='offer_funnel', desc='offer_funnel:offer_clicked_30d'),
    FeatureSpec(name='paywall_opened_7d', dtype='float', group='offer_funnel', desc='offer_funnel:paywall_opened_7d'),
    FeatureSpec(name='paywall_closed_7d', dtype='float', group='offer_funnel', desc='offer_funnel:paywall_closed_7d'),
    FeatureSpec(name='paywall_bounce_rate_7d', dtype='float', group='offer_funnel', desc='offer_funnel:paywall_bounce_rate_7d'),
    FeatureSpec(name='offer_ctr_7d', dtype='float', group='offer_funnel', desc='offer_funnel:offer_ctr_7d'),
    FeatureSpec(name='purchase_attempts_30d', dtype='int', group='payments', desc='payments:purchase_attempts_30d'),
    FeatureSpec(name='purchase_success_30d', dtype='int', group='payments', desc='payments:purchase_success_30d'),
    FeatureSpec(name='purchase_fail_30d', dtype='int', group='payments', desc='payments:purchase_fail_30d'),
    FeatureSpec(name='purchase_conv_30d', dtype='float', group='payments', desc='payments:purchase_conv_30d'),
    FeatureSpec(name='refunds_180d', dtype='float', group='payments', desc='payments:refunds_180d'),
    FeatureSpec(name='chargebacks_365d', dtype='float', group='payments', desc='payments:chargebacks_365d'),
    FeatureSpec(name='avg_order_value_365d', dtype='float', group='payments', desc='payments:avg_order_value_365d'),
    FeatureSpec(name='total_revenue_365d', dtype='float', group='payments', desc='payments:total_revenue_365d'),
    FeatureSpec(name='days_since_last_purchase', dtype='int', group='payments', desc='payments:days_since_last_purchase'),
    FeatureSpec(name='payment_method_diversity_365d', dtype='float', group='payments', desc='payments:payment_method_diversity_365d'),
]
