"""Autopilot onboarding (canonical).

This package defines the UX-safe onboarding schema and a deterministic state machine.
It contains **no side effects** and can be used from Telegram, Web, or API entrypoints.
"""

from __future__ import annotations

from .schema import (
    BudgetChoice as BudgetChoice,
    Diagnostics as Diagnostics,
    HasClientsChoice as HasClientsChoice,
    RegionChoice as RegionChoice,
)
from .state_machine import (
    OnboardingSession as OnboardingSession,
    OnboardingStep as OnboardingStep,
    OnboardingTransition as OnboardingTransition,
    advance_with_callback as advance_with_callback,
    advance_with_text as advance_with_text,
    session_from_settings as session_from_settings,
    session_to_settings as session_to_settings,
)

