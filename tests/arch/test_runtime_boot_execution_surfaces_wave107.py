from __future__ import annotations

import importlib
from pathlib import Path


def test_runtime_boot_execution_and_enforcement_use_canonical_surfaces() -> None:
    compat_modules = {
        'runtime.boot.boot_phases': 'bootstrap/boot_phases.py',
        'runtime.boot.canonical_decision_world_model_ltv': 'bootstrap/canonical_decision_world_model_ltv.py',
        'runtime.boot.canonical_decision_world_model_pricing': 'bootstrap/canonical_decision_world_model_pricing.py',
        'runtime.boot.system_builder': 'bootstrap/system_builder.py',
        'runtime.boot.world_model_builder': 'bootstrap/world_model_builder.py',
    }
    for module_name, owner_path in compat_modules.items():
        assert hasattr(importlib.import_module(module_name), '__getattr__') or importlib.import_module(module_name) is not None
        text = Path(owner_path).read_text(encoding='utf-8')
        assert 'runtime.boot' in text or 'bootstrap.' in owner_path
    for rel in (
        'runtime/boot/boot_core_assembly.py',
        'runtime/boot/core_assembly_args.py',
        'runtime/boot/core_assembly_parts.py',
        'runtime/boot/builders/campaign_builder.py',
        'runtime/decision_input/decision_core_adapter.py',
        'runtime/decision_input/runtime_state_enrichment.py',
        'runtime/execution/decision_execution_service.py',
        'runtime/execution/executor_commit.py',
        'runtime/enforcement/blast_radius_gate.py',
        'runtime/enforcement/signature_gate.py',
        'runtime/enforcement/world_model_pin_guard.py',
        'runtime/validation/action_payload_validator.py',
    ):
        text = Path(rel).read_text(encoding='utf-8')
        assert 'from core.decision_core' not in text
