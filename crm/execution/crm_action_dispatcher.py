from __future__ import annotations

from crm.actions.crm_append_note_action import CrmAppendNoteAction
from crm.actions.crm_create_pipeline_action import CrmCreatePipelineAction
from crm.actions.crm_upsert_contact_action import CrmUpsertContactAction
from crm.actions.crm_upsert_deal_action import CrmUpsertDealAction
from crm.actions.crm_upsert_lead_action import CrmUpsertLeadAction


class CrmActionDispatcher:
    def dispatch(self, action) -> str:
        if isinstance(action, CrmCreatePipelineAction):
            return 'pipeline'
        if isinstance(action, CrmUpsertLeadAction):
            return 'lead'
        if isinstance(action, CrmUpsertContactAction):
            return 'contact'
        if isinstance(action, CrmUpsertDealAction):
            return 'deal'
        if isinstance(action, CrmAppendNoteAction):
            return 'note'
        raise TypeError(f'Unsupported CRM action: {type(action)!r}')
