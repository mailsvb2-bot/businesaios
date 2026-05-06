from __future__ import annotations

import sys

from interfaces.messaging._shared.package_surface import install_channel_package_namespace

PROVIDER = "sms"
ENV_PREFIX = "SMS"
DEFAULT_MODE = "webhook"

__getattr__, __dir__, __all__ = install_channel_package_namespace(
    sys.modules[__name__],
    provider=PROVIDER,
    env_prefix=ENV_PREFIX,
    default_mode=DEFAULT_MODE,
)
