"""Ads platform layer.

This package contains infrastructure concerns for Ads connectors:
- token storage (OAuth)
- secret vault adapters

Core/business logic lives under `core/growth/*`.
"""

from .token_store import OAuthToken, AdsTokenStore, SecretVault
from .sqlite_token_store import SqliteAdsTokenStore
from .vault_env import EnvSecretVault
