from __future__ import annotations

import importlib
from pathlib import Path


def test_runtime_boot_internal_modules_use_runtime_boot_not_public_api() -> None:
    targets = (
        'runtime/boot/boot_core_assembly.py',
        'runtime/boot/boot_guard.py',
        'runtime/boot/core_assembly_args.py',
        'runtime/boot/core_assembly_parts.py',
        'runtime/boot/builders/campaign_builder.py',
    )
    for rel in targets:
        text = Path(rel).read_text(encoding='utf-8')
        assert 'from runtime.boot.public_api import' not in text, rel
    for module_name in (
        'runtime.boot.boot_phases',
        'runtime.boot.canonical_decision_world_model_ltv',
        'runtime.boot.canonical_decision_world_model_pricing',
        'runtime.boot.system_builder',
        'runtime.boot.world_model_builder',
    ):
        assert importlib.import_module(module_name) is not None
