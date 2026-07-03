from __future__ import annotations

from dataclasses import dataclass

CANON_COMPAT_SHIM = True

@dataclass(frozen=True)
class MarketingBanditPolicy:
    default_step_key: str = "tariffs_viewed"
    default_window_days: int = 30
    default_attribution_window_ms: int = 24 * 60 * 60 * 1000
    exposure_prior_beta: float = 1.0
    prior_alpha: float = 1.0
    prior_beta: float = 1.0
    negative_signal_beta: float = 0.2
    payment_success_alpha: float = 2.0
    access_granted_alpha: float = 1.5
    tariff_selected_alpha: float = 0.3
    audio_progress_alpha: float = 0.5
    audio_progress_threshold: float = 0.80
    fast_followup_window_ms: int = 4_000
    fast_followup_multiplier: float = 1.2
    hesitation_window_ms: int = 120_000
    hesitation_multiplier: float = 0.8
    fast_purchase_window_ms: int = 600_000
    fast_purchase_multiplier: float = 1.5
    medium_purchase_window_ms: int = 3_600_000
    medium_purchase_multiplier: float = 1.2
    variants: tuple[str, str] = ("a", "b")
    success_events: tuple[str, ...] = (
        "payment_succeeded",
        "payment_captured",
        "access_granted",
        "tariff_selected",
        "audio_progress",
    )
    negative_events: tuple[str, ...] = ("close_tariffs", "back", "menu_main")

    @property
    def outcome_events(self) -> tuple[str, ...]:
        return self.success_events + self.negative_events

    @property
    def relevant_event_types(self) -> tuple[str, ...]:
        return self.outcome_events

    @property
    def variant_priors(self) -> dict[str, dict[str, float]]:
        return {
            variant: {"alpha": float(self.prior_alpha), "beta": float(self.prior_beta)}
            for variant in self.variants
        }


DEFAULT_MARKETING_BANDIT_POLICY = MarketingBanditPolicy()
