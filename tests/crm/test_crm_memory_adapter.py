from crm.memory.crm_business_memory_adapter import CrmBusinessMemoryAdapter


def test_memory_adapter_projects_facts_only():
    projected = CrmBusinessMemoryAdapter().project({}, projection={'verified_action_count': 3})
    assert projected['crm']['verified_action_count'] == 3
