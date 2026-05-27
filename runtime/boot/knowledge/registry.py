CANON_BOOT_WIRING_ONLY = True


from runtime.knowledge import KnowledgeService


def build_knowledge_service(event_store, readers, writers):
    # Constructor injection для knowledge-сервисов
    return KnowledgeService(event_store=event_store, readers=readers, writers=writers)
