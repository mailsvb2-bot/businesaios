from __future__ import annotations

"""Autopilot onboarding (canonical).

This package defines the UX-safe onboarding schema and a deterministic state machine.
It contains **no side effects** and can be used from Telegram, Web, or API entrypoints.
"""

from .schema import BudgetChoice, Diagnostics, HasClientsChoice, RegionChoice
from .state_machine import (
    OnboardingSession,
    OnboardingStep,
    OnboardingTransition,
    advance_with_callback,
    advance_with_text,
    session_from_settings,
    session_to_settings,
)
