from __future__ import annotations

import ast
from pathlib import Path

from application.document.projector import CANON_DOCUMENT_PROJECTOR
from application.document.registry import CANON_DOCUMENT_LIFECYCLE_OWNER
from canon.business_ontology_inventory import ontology_ownership_by_entity

ROOT=Path(__file__).resolve().parents[2]
PRODUCTION_ROOTS=('application','runtime','storage','core','adapters','billing','crm')
REGISTRY = Path('application/document/registry.py')
FACTS = Path('application/document/facts.py')
FACT_TYPES={'document.created','document.revised','document.archived'}

def _python_files():
    for name in PRODUCTION_ROOTS:
        root=ROOT/name
        if root.exists():
            yield from root.rglob('*.py')

def test_document_inventory_has_single_owner():
    row=ontology_ownership_by_entity()['Document']
    assert CANON_DOCUMENT_LIFECYCLE_OWNER and CANON_DOCUMENT_PROJECTOR
    assert row.authoritative_module=='contracts.document'
    assert row.storage_owner=='runtime.platform.event_store'
    assert row.allowed_writers==('application.document.registry',)
    assert row.allowed_readers==('application.document.projector',)

def test_document_owner_marker_is_unique():
    owners=[]
    for path in _python_files():
        tree=ast.parse(path.read_text(encoding='utf-8'), filename=str(path))
        for node in tree.body:
            if isinstance(node,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='CANON_DOCUMENT_LIFECYCLE_OWNER' for t in node.targets) and isinstance(node.value,ast.Constant) and node.value.value is True:
                owners.append(path.relative_to(ROOT))
    assert owners==[REGISTRY]

def test_document_fact_vocabulary_has_one_owner():
    owners=set()
    for path in _python_files():
        tree=ast.parse(path.read_text(encoding='utf-8'), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node,ast.Constant) and isinstance(node.value,str) and node.value in FACT_TYPES:
                owners.add(path.relative_to(ROOT))
    assert owners=={FACTS}

def test_document_registry_reuses_artifact_and_shared_event_owners():
    src=(ROOT/REGISTRY).read_text(encoding='utf-8')
    assert 'ArtifactProjector' in src and 'EventFactLifecycleWriter' in src
    assert 'append_transition_once' in src
    assert 'BusinessFactV1(' not in src and 'ArtifactStore' not in src

def test_bootstrap_wires_document_to_existing_event_store():
    src=(ROOT/'runtime/business_autonomy/bootstrap.py').read_text(encoding='utf-8')
    assert "DocumentRegistry(event_store=customer_event_store, idempotency_store=distributed['idempotency'])" in src
    assert 'service._document_registry = document_registry' in src
