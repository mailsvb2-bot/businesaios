from __future__ import annotations

import observability.logger as root_logging
import runtime.platform.support.observability.logging as runtime_logging
from runtime.messaging_policy.preference_loader import load_channel_preference as canonical_load_preference
from runtime.messaging_preferences.load_preference import load_channel_preference as compat_load_preference
from runtime.platform.support.contracts.promotion_contract import PromotionDecision as compat_promotion
from runtime.platform.support.optimization.promotion_decision import PromotionDecision as canonical_promotion


def test_logging_surfaces_resolve_same_objects() -> None:
    assert runtime_logging.get_logger is root_logging.get_logger
    assert runtime_logging.log_kv is root_logging.log_kv


def test_promotion_surfaces_resolve_same_class() -> None:
    assert compat_promotion is canonical_promotion


def test_messaging_preference_surface_resolves_same_callable() -> None:
    assert compat_load_preference is canonical_load_preference
