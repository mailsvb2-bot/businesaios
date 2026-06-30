"""Small sync/async bridge for canonical sync entrypoints.

Delegates to the shared canonical bridge so marketing code does not drift from
other sync entrypoints such as runtime boot/apply surfaces.
"""

from __future__ import annotations


from typing import TypeVar
from collections.abc import Awaitable

import shared.asyncio_bridge as _shared_asyncio_bridge

T = TypeVar("T")


def run_awaitable_sync(awaitable: Awaitable[T]) -> T:
    return _shared_asyncio_bridge.run_awaitable_sync(awaitable, thread_name_prefix="marketing-llm-sync")
