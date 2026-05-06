from __future__ import annotations

from interfaces.messaging._shared import map_delivery_result


def map_result(*, msg, raw):
    return map_delivery_result(msg=msg, raw=raw)
