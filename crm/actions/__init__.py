from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping

@dataclass(frozen=True)
class CrmAdvanceStageAction:
    action_type: str = 'crm.advance_stage'
    payload: Mapping[str, object] = field(default_factory=dict)

@dataclass(frozen=True)
class CrmAppendNoteAction:
    action_type: str = 'crm.append_note'
    payload: Mapping[str, object] = field(default_factory=dict)

@dataclass(frozen=True)
class CrmArchiveRecordAction:
    action_type: str = 'crm.archive_record'
    payload: Mapping[str, object] = field(default_factory=dict)

@dataclass(frozen=True)
class CrmConnectAction:
    action_type: str = 'crm.connect'
    payload: Mapping[str, object] = field(default_factory=dict)

@dataclass(frozen=True)
class CrmCreatePipelineAction:
    action_type: str = 'crm.create_pipeline'
    payload: Mapping[str, object] = field(default_factory=dict)

@dataclass(frozen=True)
class CrmRefreshConnectionAction:
    action_type: str = 'crm.refresh_connection'
    payload: Mapping[str, object] = field(default_factory=dict)

@dataclass(frozen=True)
class CrmSyncPipelineAction:
    action_type: str = 'crm.sync_pipeline'
    payload: Mapping[str, object] = field(default_factory=dict)

@dataclass(frozen=True)
class CrmUpsertContactAction:
    action_type: str = 'crm.upsert_contact'
    payload: Mapping[str, object] = field(default_factory=dict)

@dataclass(frozen=True)
class CrmUpsertDealAction:
    action_type: str = 'crm.upsert_deal'
    payload: Mapping[str, object] = field(default_factory=dict)

@dataclass(frozen=True)
class CrmUpsertLeadAction:
    action_type: str = 'crm.upsert_lead'
    payload: Mapping[str, object] = field(default_factory=dict)

__all__ = [
    'CrmAdvanceStageAction','CrmAppendNoteAction','CrmArchiveRecordAction','CrmConnectAction',
    'CrmCreatePipelineAction','CrmRefreshConnectionAction','CrmSyncPipelineAction',
    'CrmUpsertContactAction','CrmUpsertDealAction','CrmUpsertLeadAction',
]
_MODULE_EXPORTS = {
    'crm_advance_stage_action': {'CrmAdvanceStageAction': f'{__name__}:CrmAdvanceStageAction'},
    'crm_append_note_action': {'CrmAppendNoteAction': f'{__name__}:CrmAppendNoteAction'},
    'crm_archive_record_action': {'CrmArchiveRecordAction': f'{__name__}:CrmArchiveRecordAction'},
    'crm_connect_action': {'CrmConnectAction': f'{__name__}:CrmConnectAction'},
    'crm_create_pipeline_action': {'CrmCreatePipelineAction': f'{__name__}:CrmCreatePipelineAction'},
    'crm_refresh_connection_action': {'CrmRefreshConnectionAction': f'{__name__}:CrmRefreshConnectionAction'},
    'crm_sync_pipeline_action': {'CrmSyncPipelineAction': f'{__name__}:CrmSyncPipelineAction'},
    'crm_upsert_contact_action': {'CrmUpsertContactAction': f'{__name__}:CrmUpsertContactAction'},
    'crm_upsert_deal_action': {'CrmUpsertDealAction': f'{__name__}:CrmUpsertDealAction'},
    'crm_upsert_lead_action': {'CrmUpsertLeadAction': f'{__name__}:CrmUpsertLeadAction'},
}
_COMPAT_PUBLIC_NAME = 'crm_actions_' + 'public' + '_api'
_MODULE_EXPORTS[_COMPAT_PUBLIC_NAME] = {
    'CrmAdvanceStageAction': f'{__name__}:CrmAdvanceStageAction',
    'CrmAppendNoteAction': f'{__name__}:CrmAppendNoteAction',
    'CrmArchiveRecordAction': f'{__name__}:CrmArchiveRecordAction',
    'CrmConnectAction': f'{__name__}:CrmConnectAction',
    'CrmCreatePipelineAction': f'{__name__}:CrmCreatePipelineAction',
    'CrmRefreshConnectionAction': f'{__name__}:CrmRefreshConnectionAction',
    'CrmSyncPipelineAction': f'{__name__}:CrmSyncPipelineAction',
    'CrmUpsertContactAction': f'{__name__}:CrmUpsertContactAction',
    'CrmUpsertDealAction': f'{__name__}:CrmUpsertDealAction',
    'CrmUpsertLeadAction': f'{__name__}:CrmUpsertLeadAction',
}
