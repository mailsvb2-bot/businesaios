from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from runtime.messaging_policy.delivery_snapshot import DeliverySnapshot
from runtime.messaging_policy.unanswered_snapshot import UnansweredSnapshot


def parse_delivery_snapshot(value: Any) -> DeliverySnapshot:
    if isinstance(value, Mapping):
        return DeliverySnapshot.from_mapping(value)
    return DeliverySnapshot()


def parse_unanswered_snapshot(value: Any) -> UnansweredSnapshot:
    if isinstance(value, Mapping):
        return UnansweredSnapshot.from_mapping(value)
    return UnansweredSnapshot()
