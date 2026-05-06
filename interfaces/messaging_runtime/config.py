from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping


@dataclass(frozen=True)
class ChannelProviderConfig:
    channel: str
    provider: str
    enabled: bool = True
    timeout_seconds: int = 30
    retry_max_attempts: int = 3
    backpressure_limit: int = 1000
    settings: Mapping[str, Any] = field(default_factory=dict)

    def validate(self) -> None:
        if not self.channel:
            raise ValueError("channel is required")
        if not self.provider:
            raise ValueError("provider is required")
        if self.timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be > 0")
        if self.retry_max_attempts <= 0:
            raise ValueError("retry_max_attempts must be > 0")
        if self.backpressure_limit <= 0:
            raise ValueError("backpressure_limit must be > 0")


@dataclass(frozen=True)
class RuntimeConfig:
    channels: Mapping[str, ChannelProviderConfig]
    defaults: Mapping[str, Any] = field(default_factory=dict)

    def validate(self) -> None:
        if not self.channels:
            raise ValueError("channels are required")
        for key, item in self.channels.items():
            if key != item.channel:
                raise ValueError(f"channel key mismatch: {key} != {item.channel}")
            item.validate()


def build_default_runtime_config() -> RuntimeConfig:
    channels = {
        "sms": ChannelProviderConfig("sms", "default-sms"),
        "whatsapp": ChannelProviderConfig("whatsapp", "default-whatsapp"),
        "email": ChannelProviderConfig("email", "default-email"),
        "messenger": ChannelProviderConfig("messenger", "default-messenger"),
        "viber": ChannelProviderConfig("viber", "default-viber"),
        "webchat": ChannelProviderConfig("webchat", "default-webchat"),
        "api_gateway": ChannelProviderConfig("api_gateway", "default-api-gateway"),
    }
    config = RuntimeConfig(channels=channels, defaults={"queue_limit": 1000, "max_attempts": 3})
    config.validate()
    return config


def load_runtime_config(raw: dict | None = None) -> RuntimeConfig:
    if not raw:
        return build_default_runtime_config()

    channels = {}
    for channel, payload in dict(raw.get("channels", {})).items():
        channels[channel] = ChannelProviderConfig(
            channel=channel,
            provider=str(payload.get("provider", "")),
            enabled=bool(payload.get("enabled", True)),
            timeout_seconds=int(payload.get("timeout_seconds", 30)),
            retry_max_attempts=int(payload.get("retry_max_attempts", 3)),
            backpressure_limit=int(payload.get("backpressure_limit", 1000)),
            settings=dict(payload.get("settings", {})),
        )
    defaults = {"queue_limit": 1000, "max_attempts": 3}
    defaults.update(dict(raw.get("defaults", {})))
    config = RuntimeConfig(channels=channels, defaults=defaults)
    config.validate()
    return config
