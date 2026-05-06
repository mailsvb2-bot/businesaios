from __future__ import annotations

from runtime.messaging.channel_types import CHANNEL_EMAIL, CHANNEL_SMS
from runtime.messaging_policy.policy_request import PolicyRequest


def _dedupe(items) -> tuple[str, ...]:
    return tuple(dict.fromkeys(str(x) for x in items if str(x).strip()))


def build_candidate_sequence(req: PolicyRequest) -> tuple[str, ...]:
    base: list[str] = []

    first = req.preferred_channel or req.preference.primary
    if first:
        base.append(first)

    if req.fallback_channels:
        for item in req.fallback_channels:
            base.append(item)
    else:
        for item in req.preference.enabled:
            if item != first:
                base.append(item)

    if req.critical:
        for item in (CHANNEL_SMS, CHANNEL_EMAIL):
            if item in req.preference.enabled:
                base.append(item)

    return _dedupe(base)
