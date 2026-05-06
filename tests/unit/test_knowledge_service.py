
def test_knowledge_service_build():
    from core.knowledge.service import KnowledgeService
    service = KnowledgeService(event_store={}, readers={}, writers={})
    assert service is not None
