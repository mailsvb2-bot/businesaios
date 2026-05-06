from __future__ import annotations

from runtime.boot.economics_boot import CANON_BOOT_WIRING_ONLY as ECONOMICS_BOOT
from runtime.boot.experiments_boot import CANON_BOOT_WIRING_ONLY as EXPERIMENTS_BOOT
from runtime.boot.finance_boot import CANON_BOOT_WIRING_ONLY as FINANCE_BOOT
from runtime.boot.governance_boot import CANON_BOOT_WIRING_ONLY as GOVERNANCE_BOOT
from runtime.boot.human_governance_boot import CANON_BOOT_WIRING_ONLY as HUMAN_GOVERNANCE_BOOT
from runtime.boot.knowledge_boot import CANON_BOOT_WIRING_ONLY as KNOWLEDGE_BOOT
from runtime.boot.learning_loop_boot import CANON_BOOT_WIRING_ONLY as LEARNING_LOOP_BOOT
from runtime.boot.product_boot import CANON_BOOT_WIRING_ONLY as PRODUCT_BOOT
from runtime.boot.simulation_boot import CANON_BOOT_WIRING_ONLY as SIMULATION_BOOT
from runtime.boot.world_model_boot import CANON_BOOT_WIRING_ONLY as WORLD_MODEL_BOOT


def test_domain_boot_markers_are_true() -> None:
    assert all([
        WORLD_MODEL_BOOT,
        ECONOMICS_BOOT,
        SIMULATION_BOOT,
        KNOWLEDGE_BOOT,
        LEARNING_LOOP_BOOT,
        PRODUCT_BOOT,
        GOVERNANCE_BOOT,
        FINANCE_BOOT,
        EXPERIMENTS_BOOT,
        HUMAN_GOVERNANCE_BOOT,
    ])
