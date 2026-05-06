from __future__ import annotations

from infra.control_plane_boot_result import ControlPlaneBootResult


def apply_control_plane_defaults(control_plane: ControlPlaneBootResult) -> None:
    control_plane.feature_flags.enable("api.execute_action.enabled")
    control_plane.feature_flags.enable("telegram.execute_action.enabled")
    control_plane.kill_switches.reset("api.execute_action")
    control_plane.kill_switches.reset("telegram.execute_action")
