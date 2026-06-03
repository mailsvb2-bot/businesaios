from __future__ import annotations

"""Canonical compat surface for headless feedback.

Kept as a thin file because arch locks inspect this exact path. The capability
view must be merged from action payload and normalized output only.
"""

from typing import Any
from collections.abc import Mapping

from execution.capability_operator_view import merge_capability_views, normalize_capability_view
from application.headless.feedback import CANON_HEADLESS_FEEDBACK_READER, SimpleHeadlessFeedbackReader


def _dictish(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def build_capability_view(*, action_payload: Mapping[str, Any] | None, result: Any, normalized: Mapping[str, Any] | None = None) -> dict[str, Any]:
    capability_view = merge_capability_views(
        action_payload,
        _dictish(getattr(result, "output", {})),
        normalized,
    )
    return normalize_capability_view(capability_view)


__all__ = ['CANON_HEADLESS_FEEDBACK_READER', 'SimpleHeadlessFeedbackReader', 'build_capability_view']
