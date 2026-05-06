from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from application.business_autonomy.provider_admin_contract import ProviderDefinition


@dataclass(frozen=True)
class ProviderMessagingBinding:
    provider_key: str
    channel: str
    required_capabilities: Mapping[str, bool]
    live_probe_supported: bool


def describe_provider_messaging_binding(provider: ProviderDefinition) -> ProviderMessagingBinding | None:
    channel = str(getattr(provider, 'messaging_channel', '') or '').strip()
    if not channel:
        return None
    capabilities = dict(getattr(provider, 'messaging_capabilities', {}) or {})
    return ProviderMessagingBinding(
        provider_key=str(provider.provider_key),
        channel=channel,
        required_capabilities={
            'plain_text': bool(capabilities.get('plain_text', True)),
            'html': bool(capabilities.get('html', False)),
            'buttons': bool(capabilities.get('buttons', False)),
            'attachments': bool(capabilities.get('attachments', False)),
            'structured_payload': bool(capabilities.get('structured_payload', False)),
            'subject_line': bool(capabilities.get('subject_line', False)),
        },
        live_probe_supported=bool(getattr(provider, 'messaging_live_probe_supported', False)),
    )
