from __future__ import annotations

"""Payment effect helpers.

External I/O stays sealed in runtime/_internal/_effects_impl.py.
"""

from dataclasses import dataclass


@dataclass
class PaymentIdempotency:
    """Namespace for idempotency helper constants."""

    terminal_marker_table: str = 'payment_terminal'
