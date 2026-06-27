"""Thin aggregator for the IRON hardening suite.

The actual assertions live under tests.iron_hardening so failures are easier
to localize and the guard layer does not accumulate into a single monolith.
"""

from __future__ import annotations

from tests.iron_hardening.suite import *  # noqa: F401,F403
