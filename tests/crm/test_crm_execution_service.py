from crm.actions.crm_upsert_contact_action import CrmUpsertContactAction
from crm.execution.crm_execution_service import CrmExecutionService


def test_execution_service_routes_contact_action():
    action = CrmUpsertContactAction(payload={'id': '1'})
    result = CrmExecutionService().execute(action, handler_map={'contact': lambda a: {'ok': True, 'id': a.payload['id']}})
    assert result['channel'] == 'crm'
