"""Physical compatibility package surface.

This package uses real files instead of import-time synthetic module generation.
"""

from __future__ import annotations

from importlib import import_module

__all__ = ['contracts', 'delayed_reward_credit', 'reward_aggregation', 'reward_audit', 'reward_calibration', 'reward_clipping', 'reward_explainer', 'reward_model', 'reward_normalization', 'reward_pipeline', 'reward_sanity_checks', 'reward_service', 'reward_signals', 'reward_versioning', 'sparse_reward_support']

for _name in __all__:
    globals()[_name] = import_module(f".{_name}", __name__)
