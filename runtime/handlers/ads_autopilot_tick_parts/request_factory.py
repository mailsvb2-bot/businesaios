from __future__ import annotations

from runtime.handlers.ads_autopilot.request_builder import build_autopilot_request


def build_safe_autopilot_request(*, payload, route):
    return build_autopilot_request(payload=payload, route=route)
