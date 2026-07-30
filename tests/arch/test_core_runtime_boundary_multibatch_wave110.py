from __future__ import annotations

import ast
import importlib
from pathlib import Path

FILES = {
    'runtime/handlers_messaging.py': ['from runtime.marketing import'],
    'bootstrap/assembly_runtime.py': ['from runtime.ads import bind_runtime_state'],
    'runtime/boot/builders/ads_apply_engine.py': [
        'from runtime.ads import',
        'from runtime.governance import FeedbackLoopGuard, ProfitMetricsService',
    ],
    'runtime/boot/builders/campaign_builder.py': ['from runtime.creative import LLMCreativeGenerator'],
    'runtime/boot/builders/marketing_llm.py': [
        'from runtime.llm import LLMAgent, LLMAgentConfig, build_runtime_llm_client, normalize_provider, resolve_runtime_llm_settings',
        'from runtime.marketing import LLMComposerConfig, MarketingLLMComposer',
    ],
    'runtime/boot/system_builder_parts/runtime_services.py': [
        'from runtime.governance import assert_governance_event_store_contract',
    ],
}


def test_runtime_boundary_files_use_runtime_public_apis_only() -> None:
    compat = importlib.import_module('runtime.boot.assembly_runtime')
    assert hasattr(compat, 'build_runtime') or hasattr(compat, '__getattr__')
    for rel, required in FILES.items():
        text = Path(rel).read_text(encoding='utf-8')
        assert 'from core.' not in text, rel
        assert 'import core.' not in text, rel
        tree = ast.parse(text, filename=rel)
        imports: dict[str, set[str]] = {}
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                imports.setdefault(node.module, set()).update(alias.name for alias in node.names)
        for needle in required:
            prefix, _, imported = needle.partition(" import")
            module = prefix.removeprefix("from ").strip()
            assert module in imports, (rel, module, imports)
            expected_names = {name.strip() for name in imported.strip().strip("()").split(",") if name.strip()}
            assert expected_names <= imports[module], (rel, module, expected_names, imports[module])
