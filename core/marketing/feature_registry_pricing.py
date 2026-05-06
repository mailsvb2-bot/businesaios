from __future__ import annotations
from core.marketing.feature_registry_shared import FeatureSpec

FEATURES = [
    FeatureSpec(name='avg_price_seen_30d', dtype='float', group='pricing', desc='pricing:avg_price_seen_30d'),
    FeatureSpec(name='min_price_seen_30d', dtype='float', group='pricing', desc='pricing:min_price_seen_30d'),
    FeatureSpec(name='max_price_seen_30d', dtype='float', group='pricing', desc='pricing:max_price_seen_30d'),
    FeatureSpec(name='discount_seen_avg_30d', dtype='int', group='pricing', desc='pricing:discount_seen_avg_30d'),
    FeatureSpec(name='trial_seen_rate_30d', dtype='float', group='pricing', desc='pricing:trial_seen_rate_30d'),
    FeatureSpec(name='price_sensitivity_index', dtype='float', group='pricing', desc='pricing:price_sensitivity_index'),
    FeatureSpec(name='premium_acceptance_index', dtype='float', group='pricing', desc='pricing:premium_acceptance_index'),
    FeatureSpec(name='bundle_acceptance_index', dtype='float', group='pricing', desc='pricing:bundle_acceptance_index'),
    FeatureSpec(name='low_band_acceptance_index', dtype='float', group='pricing', desc='pricing:low_band_acceptance_index'),
    FeatureSpec(name='standard_band_acceptance_index', dtype='float', group='pricing', desc='pricing:standard_band_acceptance_index'),
]
