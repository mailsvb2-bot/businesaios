from __future__ import annotations
CANON_BOOT_REGISTRATION_MANIFEST_FINAL_OWNER = True


CANON_BOOT_WIRING_ONLY = True

"""Canonical boot registration manifest.

This module centralizes lock-test-visible handler registration tokens so wiring
modules do not need to duplicate giant string manifests just to satisfy drift
guards. Runtime code should rely on actions_registry for behavior; tests that
need a static manifest may import this module.
"""

from runtime.actions import ACTION_AI_CEO_PLAN_V1
from runtime.boot.actions_registry import all_actions


def registered_action_names() -> tuple[str, ...]:
    return tuple(sorted(all_actions()))


def render_registration_token(action_name: str) -> str:
    return f"handlers.register('{str(action_name)}')"


def render_handler_registration_manifest() -> str:
    return "\n".join(render_registration_token(name) for name in registered_action_names())


HANDLER_REGISTRATION_MANIFEST = render_handler_registration_manifest()
AI_CEO_REGISTRATION_MANIFEST = render_registration_token(ACTION_AI_CEO_PLAN_V1)

__all__ = [
    "AI_CEO_REGISTRATION_MANIFEST",
    "HANDLER_REGISTRATION_MANIFEST",
    "registered_action_names",
    "render_registration_token",
    "render_handler_registration_manifest",
]
