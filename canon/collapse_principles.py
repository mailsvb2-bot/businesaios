"""Canonical collapse principles (hard invariants).

Epigraph:
1) One DecisionCore.
2) One canonical state/world-model path.
3) One guarded execution path.
4) One boot/factory/registration owner.
5) No second brain.
6) No allowlist patches just to make status green.
7) No deletion of user-facing functionality.
8) Any collapse means moving capability to the single owner, not losing capability.

Core collapse law:
1) Collapse must reduce project size (files/lines/artifacts).
2) No loss of semantic functionality (including formulas and unique logic).
"""

CANON_COLLAPSE_EPIGRAPH = (
    "one_decision_core",
    "one_canonical_state_world_model_path",
    "one_guarded_execution_path",
    "one_boot_factory_registration_owner",
    "no_second_brain",
    "no_allowlist_patches_for_green_status",
    "no_user_facing_functionality_deletion",
    "collapse_moves_capability_to_single_owner_without_loss",
)

CANON_COLLAPSE_PRINCIPLES = {
    "must_reduce_project_size": True,
    "no_functional_regression": True,
    "preserve_all_semantics": True,
    "preserve_all_formulas": True,
    "preserve_all_user_functionality": True,
    "single_owner_collapse_only": True,
}
