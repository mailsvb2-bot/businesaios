"""Typed enqueue helpers and legacy compatibility wrappers.

Responsibility:
  - Named enqueue_ack / enqueue_ux / enqueue_system / … helpers
  - Legacy enqueue_high / enqueue_normal (DeprecationWarning)

Depends on the core `enqueue()` method supplied by TelegramOutboundQueue.
"""

from __future__ import annotations

import warnings
from collections.abc import Callable
from typing import Any

from interfaces.telegram.outbound.outbound_enqueue_helpers import (
    enqueue_best_effort_with_suppression,
    parse_legacy_task,
)


class OutboundEnqueueApiMixin:
    """Typed per-kind enqueue helpers.

    Mix into TelegramOutboundQueue (which supplies self.enqueue() and
    self._self_heal, self._counters_lock, self._dropped_best_effort,
    self._maybe_alert).
    """

    _warned_legacy_enqueue: bool = False

    # ------------------------------------------------------------------
    # Typed helpers (current API)
    # ------------------------------------------------------------------

    def enqueue_ack(
        self,
        *,
        method: str,
        chat_id: int | None,
        fn: Callable[[], Any],
        meta: dict[str, Any] | None = None,
        critical: bool = False,
    ) -> bool:
        return self.enqueue(
            method=method, chat_id=chat_id, fn=fn, meta=meta,
            critical=critical, priority=self.PRIO_ACK, kind="ack",
        )

    def enqueue_ux(
        self,
        *,
        method: str,
        chat_id: int | None,
        fn: Callable[[], Any],
        meta: dict[str, Any] | None = None,
        critical: bool = True,
    ) -> bool:
        return self.enqueue(
            method=method, chat_id=chat_id, fn=fn, meta=meta,
            critical=critical, priority=self.PRIO_UX, kind="ux",
        )

    def enqueue_system(
        self,
        *,
        method: str,
        chat_id: int | None,
        fn: Callable[[], Any],
        meta: dict[str, Any] | None = None,
        critical: bool = True,
    ) -> bool:
        return self.enqueue(
            method=method, chat_id=chat_id, fn=fn, meta=meta,
            critical=critical, priority=self.PRIO_SYSTEM, kind="system",
        )

    def enqueue_payments(
        self,
        *,
        method: str,
        chat_id: int | None,
        fn: Callable[[], Any],
        meta: dict[str, Any] | None = None,
        critical: bool = True,
    ) -> bool:
        return self.enqueue(
            method=method, chat_id=chat_id, fn=fn, meta=meta,
            critical=critical, priority=self.PRIO_PAYMENTS, kind="payments",
        )

    def enqueue_marketing(
        self,
        *,
        method: str,
        chat_id: int | None,
        fn: Callable[[], Any],
        meta: dict[str, Any] | None = None,
    ) -> bool:
        return enqueue_best_effort_with_suppression(
            self,
            method=method,
            chat_id=chat_id,
            fn=fn,
            meta=meta,
            priority=self.PRIO_MARKETING,
            kind="marketing",
        )

    def enqueue_bulk(
        self,
        *,
        method: str,
        chat_id: int | None,
        fn: Callable[[], Any],
        meta: dict[str, Any] | None = None,
    ) -> bool:
        return enqueue_best_effort_with_suppression(
            self,
            method=method,
            chat_id=chat_id,
            fn=fn,
            meta=meta,
            priority=self.PRIO_BULK,
            kind="bulk",
        )

    def enqueue_analytics(
        self,
        *,
        method: str,
        chat_id: int | None,
        fn: Callable[[], Any],
        meta: dict[str, Any] | None = None,
    ) -> bool:
        return enqueue_best_effort_with_suppression(
            self,
            method=method,
            chat_id=chat_id,
            fn=fn,
            meta=meta,
            priority=self.PRIO_ANALYTICS,
            kind="analytics",
        )

    def is_marketing_suppressed(self) -> bool:
        return self._self_heal.is_suppressed()

    # ------------------------------------------------------------------
    # Legacy compatibility wrappers (deprecated)
    # ------------------------------------------------------------------

    def enqueue_high(self, task: Any) -> bool:
        """Deprecated. Use enqueue_ux() or enqueue_ack()."""
        if not OutboundEnqueueApiMixin._warned_legacy_enqueue:
            OutboundEnqueueApiMixin._warned_legacy_enqueue = True
            warnings.warn(
                "enqueue_high/enqueue_normal are deprecated; use enqueue_ux/enqueue_system/…",
                DeprecationWarning,
                stacklevel=2,
            )
        method, chat_id, fn, meta, critical, prio = parse_legacy_task(
            task,
            default_priority=self.PRIO_UX,
        )
        if prio not in {self.PRIO_ACK, self.PRIO_UX}:
            prio = self.PRIO_UX
        return self.enqueue(method=method, chat_id=chat_id, fn=fn, meta=meta, critical=critical, priority=prio)

    def enqueue_normal(self, task: Any) -> bool:
        """Deprecated. Use enqueue_system() or enqueue()."""
        if not OutboundEnqueueApiMixin._warned_legacy_enqueue:
            OutboundEnqueueApiMixin._warned_legacy_enqueue = True
            warnings.warn(
                "enqueue_high/enqueue_normal are deprecated; use enqueue_ux/enqueue_system/…",
                DeprecationWarning,
                stacklevel=2,
            )
        method, chat_id, fn, meta, critical, prio = parse_legacy_task(
            task,
            default_priority=self.PRIO_NORMAL,
        )
        if prio in {self.PRIO_ACK, self.PRIO_UX}:
            prio = self.PRIO_NORMAL
        return self.enqueue(method=method, chat_id=chat_id, fn=fn, meta=meta, critical=critical, priority=prio)
