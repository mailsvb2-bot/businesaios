from __future__ import annotations

"""Autopilot onboarding (canonical).

This package defines the UX-safe onboarding schema and a deterministic state machine.
It contains **no side effects** and can be used from Telegram, Web, or API entrypoints.
"""

from .schema import Diagnostics, BudgetChoice, RegionChoice, HasClientsChoice
from .state_machine import (
    OnboardingStep,
    OnboardingSession,
    OnboardingTransition,
    advance_with_text,
    advance_with_callback,
    session_from_settings,
    session_to_settings,
)
