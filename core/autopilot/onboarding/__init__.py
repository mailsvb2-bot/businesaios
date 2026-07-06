"""Autopilot onboarding (canonical).

This package defines the UX-safe onboarding schema and a deterministic state machine.
It contains **no side effects** and can be used from Telegram, Web, or API entrypoints.
"""

from __future__ import annotations

from .schema import (
    BudgetChoice as BudgetChoice,
)
from .schema import (
    Diagnostics as Diagnostics,
)
from .schema import (
    HasClientsChoice as HasClientsChoice,
)
from .schema import (
    RegionChoice as RegionChoice,
)
from .state_machine import (
    OnboardingSession as OnboardingSession,
)
from .state_machine import (
    OnboardingStep as OnboardingStep,
)
from .state_machine import (
    OnboardingTransition as OnboardingTransition,
)
from .state_machine import (
    advance_with_callback as advance_with_callback,
)
from .state_machine import (
    advance_with_text as advance_with_text,
)
from .state_machine import (
    session_from_settings as session_from_settings,
)
from .state_machine import (
    session_to_settings as session_to_settings,
)

