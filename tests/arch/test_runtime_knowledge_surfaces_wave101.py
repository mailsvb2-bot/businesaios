from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

FORBIDDEN_IMPORTS = {
    'runtime/boot/knowledge_bundle.py': ('from core.knowledge',),
    'runtime/boot/knowledge_wiring.py': ('from core.knowledge',),
    'runtime/handlers/knowledge_build.py': ('from core.knowledge',),
    'runtime/handlers/knowledge_explain.py': ('from core.knowledge',),
    'runtime/boot/knowledge/registry.py': ('from core.knowledge',),
}

REQUIRED_IMPORTS = {
    'runtime/boot/knowledge_bundle.py': ('from runtime.knowledge import (',),
    'runtime/boot/knowledge_wiring.py': ('from runtime.knowledge import (',),
    'runtime/handlers/knowledge_build.py': ('from runtime.knowledge import Lesson, LessonDraft',),
    'runtime/handlers/knowledge_explain.py': ('from runtime.knowledge import MemoryRetrieval',),
    'runtime/boot/knowledge/registry.py': ('from runtime.knowledge import KnowledgeService',),
}


def _read(rel_path: str) -> str:
    return (ROOT / rel_path).read_text(encoding='utf-8')


def test_runtime_knowledge_surfaces_do_not_import_core_directly() -> None:
    for rel_path, patterns in FORBIDDEN_IMPORTS.items():
        text = _read(rel_path)
        for pattern in patterns:
            assert pattern not in text, f'{rel_path} must not import {pattern} directly'


def test_runtime_knowledge_surfaces_use_public_api() -> None:
    for rel_path, patterns in REQUIRED_IMPORTS.items():
        text = _read(rel_path)
        for pattern in patterns:
            assert pattern in text, f'{rel_path} must import via runtime public surface: {pattern}'
