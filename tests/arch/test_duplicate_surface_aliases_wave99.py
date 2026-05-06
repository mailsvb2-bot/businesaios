from __future__ import annotations

from pathlib import Path


def test_runtime_logging_surface_is_thin_alias_to_root_logger() -> None:
    content = Path("runtime/platform/support/observability/logging.py").read_text(encoding="utf-8")
    assert "from observability.logger import" in content
    assert "def __getattr__" in content


def test_promotion_surfaces_share_single_contract_owner() -> None:
    contract = Path("runtime/platform/support/contracts/promotion_contract.py").read_text(encoding="utf-8")
    assert "optimization.promotion_decision import PromotionDecision" in contract
    optimization_surface = Path("runtime/platform/support/optimization/promotion_decision.py").read_text(encoding="utf-8")
    assert "class PromotionDecision" in optimization_surface


def test_messaging_preference_compat_module_is_lazy_alias() -> None:
    content = Path("runtime/messaging_preferences/load_preference.py").read_text(encoding="utf-8")
    assert "preference_loader import load_channel_preference" in content
    assert "def __getattr__" in content
