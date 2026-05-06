from pathlib import Path


def test_control_plane_is_split() -> None:
    for rel in (
        "infra/feature_flags.py",
        "infra/feature_flag_store.py",
        "infra/rollout_policy.py",
        "infra/rollout_models.py",
        "infra/kill_switches.py",
        "infra/maintenance_mode.py",
        "infra/runtime_guardrails.py",
        "infra/release_fingerprint.py",
        "infra/control_plane_boot.py",
        "infra/control_plane_boot_result.py",
    ):
        assert Path(rel).exists(), rel
