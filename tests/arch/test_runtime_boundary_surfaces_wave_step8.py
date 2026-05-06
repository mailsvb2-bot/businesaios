from pathlib import Path


FILES = {
    'runtime/recovery.py': ('from runtime.recovery_support import', 'from core.observability.errors import', 'from core.ai.decision_archive import'),
    'runtime/handlers_messaging.py': ('from runtime.marketing import', 'from core.marketing.llm_prompt_builder import', 'from core.marketing.llm_templates import'),
    'runtime/guard_init_support.py': ('from runtime.time import SystemClock', 'from core.runtime.clock import SystemClock'),
    'runtime/inmemory_ledger.py': ('from runtime.ledger import GENESIS, entry_hash, payload_hash', 'from core.utils.hash_chain import', 'from core.utils.canonical import payload_hash'),
}


def test_runtime_step8_boundary_surfaces_are_used() -> None:
    root = Path(__file__).resolve().parents[2]
    for rel, checks in FILES.items():
        content = (root / rel).read_text(encoding='utf-8')
        must_have, *must_not_have = checks
        assert must_have in content, rel
        for forbidden in must_not_have:
            assert forbidden not in content, rel


def test_runtime_root_aliases_retired_boundary_shims() -> None:
    root = Path(__file__).resolve().parents[2]
    text = (root / 'runtime/__init__.py').read_text(encoding='utf-8')
    assert '"bootstrap_prod_guards": "bootstrap.prod_guards"' in text
