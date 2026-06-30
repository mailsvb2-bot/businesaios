"""Explicit compat module for runtime boot safety imports.

This keeps direct imports stable without relying on lazy package attribute
resolution only.
"""

from __future__ import annotations

from bootstrap.safety_control_boot import build_runtime_action_controls, build_safety_control_runtime

__all__ = ["build_runtime_action_controls", "build_safety_control_runtime"]

