"""Feature flags for runtime.

Design goals:
- Safe-by-default: anything that can trigger side-effects or extra costs is OFF unless explicitly enabled.
- Import-safe: this module must be safe to import during boot.
- Simple: environment variables only; no network, no file IO.

Conventions:
- Flags are enabled via <NAME>_ENABLED=1/true/yes/on
- Defaults are conservative (False) unless a flag is purely diagnostic.
"""

from __future__ import annotations

from runtime.platform.config.env_flags import env_bool


class FeatureFlags:
    """Static feature flags evaluated from environment variables."""

    # Retention / marketing decision adapter (may change UX + add compute)
    RETENTION: bool = env_bool("RETENTION_ENABLED", False)

    # Marketing bandit read model (admin surface only; may add reads)
    MARKETING_BANDIT: bool = env_bool("MARKETING_BANDIT_ENABLED", False)

    # Allow LLM marketing port usage if wired (kept OFF by default).
    LLM_MARKETING: bool = env_bool("LLM_MARKETING_ENABLED", False)

    # Use async outbound queue for Telegram transport (OFF unless you wire it).
    ASYNC_TELEGRAM: bool = env_bool("ASYNC_TELEGRAM_ENABLED", False)

    # Scheduled outbox delivery loop (OFF unless you run a worker).
    SCHEDULED_OUTBOX: bool = env_bool("SCHEDULED_OUTBOX_ENABLED", False)

    # Diagnostics: latency spans are already emitted; this toggles admin aggregation surface.
    LATENCY_AI: bool = env_bool("LATENCY_AI_ENABLED", True)

    # Autopricing suggestions for tariffs (read-only; affects displayed prices).
    AUTOPRICING: bool = env_bool("AUTOPRICING_ENABLED", False)

    # Maintain continuous user_state projection in the event store (dev/prod safe).
    CONTINUOUS_STATE: bool = env_bool("CONTINUOUS_STATE_ENABLED", True)

    # Autopricing via RL picker (read-only; affects displayed prices).
    AUTOPRICING_RL: bool = env_bool("AUTOPRICING_RL_ENABLED", False)

    # Stop-loss gate for RL autopricing suggestions.
    AUTOPRICING_RL_STOPLOSS: bool = env_bool("AUTOPRICING_RL_STOPLOSS_ENABLED", False)

    @classmethod
    def is_enabled(cls, name: str, default: bool = False) -> bool:
        """Dynamic access to <NAME>_ENABLED env flags.

        This keeps older call-sites working without proliferating hardcoded attributes.
        """
        try:
            return env_bool(f"{str(name).strip()}_ENABLED", bool(default))
        except Exception:
            return bool(default)
