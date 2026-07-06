"""Canonical config registry.

Unifies settings + feature flags + YAML loading + tenant env access behind one
access point so boot/runtime code avoids parallel config paths.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from runtime.platform.config.env_tenant_config import EnvTenantConfigStore
from runtime.platform.config.feature_flags import FeatureFlags
from runtime.platform.config.settings_loader import load_settings
from runtime.platform.config.yaml_loader import load_yaml


@dataclass(frozen=True)
class ConfigRegistry:
    """Single config access point for runtime assembly."""

    def settings(self, *, force_reload: bool = False):
        return load_settings(force_reload=force_reload)

    def feature_flags(self) -> type[FeatureFlags]:
        return FeatureFlags

    def yaml_from_text(self, raw: str) -> Any:
        return load_yaml(raw)

    def yaml_from_path(self, path: str | Path) -> Any:
        p = Path(path)
        return load_yaml(p.read_text(encoding="utf-8"))

    def tenant_env(self) -> EnvTenantConfigStore:
        return EnvTenantConfigStore()


CONFIG = ConfigRegistry()

__all__ = ["ConfigRegistry", "CONFIG"]
