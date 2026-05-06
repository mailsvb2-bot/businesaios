from __future__ import annotations

"""ProductResolver (deterministic, no side-effects).

Goal:
  Allow the Engine to serve multiple organizations without binding the core to any single product.

Rules (deterministic priority):
  1) /start <token> (deep-link) selects product/domain
  2) user settings (read-model) may pin domain/config
  3) fallback to env PRODUCT_CONFIG

This resolver MUST NOT write anything. Persistence is handled elsewhere
(event-sourced) if/when you decide to add it.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Mapping, Optional

import logging

from runtime.platform.config.env_flags import env_str
from products.product_loader import ProductLoader

_log = logging.getLogger(__name__)


def _token_to_config(token: str) -> Optional[str]:
    t = (token or "").strip().lower()
    if not t:
        return None
    # allow passing config filename directly
    if t.endswith(".yaml"):
        return t
    # common aliases
    if t in {"org", "organization", "organization_platform", "workspace", "platform", "businesaios"}:
        return "organization_platform.yaml"
    if t in {"sales", "salesbot"}:
        return "sales.yaml"
    if t in {"retention", "ret", "retentionbot"}:
        return "retention.yaml"
    # allow domain token (exact)
    if t in {"organization_platform", "sales", "retention"}:
        return f"{t}.yaml"
    return None


@dataclass(frozen=True)
class ProductResolver:
    """Resolve ProductContext for a specific update/user (read-only)."""

    base_dir: Path
    default_config: str

    def resolve(
        self,
        *,
        command: Optional[str],
        args: str,
        user_settings: Mapping[str, Any] | None,
    ) -> Dict[str, Any]:
        # 1) /start token
        try:
            if (command or "").strip().lower() == "/start":
                token = (args or "").strip().split(maxsplit=1)[0] if (args or "").strip() else ""
                cfg = _token_to_config(token)
                if cfg:
                    return dict(self._load(cfg))
        except (ValueError, KeyError, OSError) as e:
            _log.warning("product_resolver: /start token resolution failed: %s", e)

        # 2) pinned via user settings (read-model)
        try:
            s = dict(user_settings or {})
            # allow either explicit config filename or domain token
            pinned_cfg = str(s.get("product_config") or "").strip()
            if pinned_cfg:
                cfg = _token_to_config(pinned_cfg) or pinned_cfg
                return dict(self._load(cfg))
            pinned_domain = str(s.get("product_domain") or s.get("domain") or "").strip()
            if pinned_domain:
                cfg2 = _token_to_config(pinned_domain)
                if cfg2:
                    return dict(self._load(cfg2))
        except (ValueError, KeyError, OSError) as e:
            _log.warning("product_resolver: user_settings resolution failed: %s", e)

        # 3) env default
        return dict(self._load(self.default_config))

    def _load(self, filename: str) -> Mapping[str, Any]:
        loader = ProductLoader(base_dir=self.base_dir)
        ctx = loader.load(str(filename))
        out = dict(ctx.as_dict())
        # keep legacy field for existing UX
        out.setdefault("name", "BusinesAIOS Workspace")
        return out


def new_resolver_from_env() -> ProductResolver:
    cfg = env_str("PRODUCT_CONFIG", "organization_platform.yaml").strip() or "organization_platform.yaml"
    return ProductResolver(base_dir=Path(__file__).parent, default_config=cfg)
