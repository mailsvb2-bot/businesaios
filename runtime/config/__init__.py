"""Runtime configuration package.

Keep startup imports deterministic and side-effect free.
Historical lightweight shims are collapsed into package-level aliases so legacy
imports stay stable without keeping duplicate files.
"""

from __future__ import annotations

from typing import Final

from runtime.lazy_namespace import install_module_aliases
from runtime.platform.config.registry import CONFIG

CANON_RUNTIME_CONFIG_NAMESPACE: Final[bool] = True


def load_settings(*, force_reload: bool = False):
    return CONFIG.settings(force_reload=force_reload)


FeatureFlags = CONFIG.feature_flags()

__all__ = [
    "CANON_RUNTIME_CONFIG_NAMESPACE",
    "FeatureFlags",
    "load_settings",
]

_COMPAT_MODULE_ALIASES = (
    "settings_loader",
    "feature_flags",
)

install_module_aliases(__name__, _COMPAT_MODULE_ALIASES)
