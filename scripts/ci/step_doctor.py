from __future__ import annotations

"""CI contract wrapper: doctor step delegates to scripts.ci.step_registry.

This file is intentionally thin. The single owner of CI step behavior remains
scripts.ci.step_registry.
"""

from scripts.ci.step_registry import run_doctor as run

__all__ = ["run"]
