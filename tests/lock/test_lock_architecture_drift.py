from __future__ import annotations

from scripts.arch_drift_detector import main


def test_architecture_drift_detector_passes():
    assert main() == 0
