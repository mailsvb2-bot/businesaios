from __future__ import annotations

"""Canonical runtime action constants.

This module owns stable action-name constants only. Declarative action rows stay in
``runtime.boot.actions_catalog`` and registry construction stays in
``runtime.boot.actions_registry``.
"""

ACTION_AI_CEO_PLAN_V1 = "ai_ceo_plan@v1"

__all__ = ["ACTION_AI_CEO_PLAN_V1"]
