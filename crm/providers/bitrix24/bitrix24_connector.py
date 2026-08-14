from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal, InvalidOperation

from crm.crm_connection_contract import CrmConnectionRef
from crm.crm_connector_contract import CrmConnector
from crm.crm_contact_contract import CrmContact
from crm.crm_deal_contract import CrmDeal
from crm.crm_note_contract import CrmNote
from crm.crm_pipeline_contract import CrmPipeline
from crm.crm_provider_contract import CrmProvider
from crm.crm_stage_contract import CrmStage
from crm.crm_verification_contract import CrmVerificationRequest, CrmVerificationResult
from crm.providers.bitrix24.bitrix24_api_config import Bitrix24ApiConfig
from crm.providers.bitrix24.bitrix24_auth_adapter import Bitrix24AuthAdapter
from crm.providers.bitrix24.bitrix24_capability_descriptor import build_bitrix24_capability_descriptor
from crm.providers.bitrix24.bitrix24_client import Bitrix24Client
from crm.providers.common.crm_oauth_token_store import CrmOAuthTokenStore, InMemoryCrmOAuthTokenStore
from crm.providers.common.crm_provider_store import CrmProviderStore


class Bitrix24Connector(CrmConnector):
    CONTACT_ENTITY_TYPE_ID = 3
    DEAL_ENTITY_TYPE_ID = 2

    def __init__(
        self,
        *,
        token_store: CrmOAuthTokenStore | None = None,
        client_id: str | None = None,
        client_secret: str | None = None,
        api_config: Bitrix24ApiConfig | None = None,
    ) -> None:
        self.provider = CrmProvider(
            provider_key='bitrix24',
            display_name='Bitrix24',
            capability_descriptor=build_bitrix24_capability_descriptor(),
        )
        self._store = CrmProviderStore('bitrix24')
        self._config = api_config or Bitrix24ApiConfig()
        self._auth: Bitrix24AuthAdapter | None = None
        if client_id and client_secret:
            self._auth = Bitrix24AuthAdapter(
                token_store=token_store or InMemoryCrmOAuthTokenStore(),
                client_id=client_id,
                client_secret=client_secret,
                api_config=self._config,
            )

    def capabilities(self):
        return self.provider.capability_descriptor

    def supports_live_api(self) -> bool:
        return self._auth is not None

    def exchange_oauth_code(self, *, secret_ref: str, authorization_code: str, redirect_uri: str) -> None:
        if self._auth is None:
            raise RuntimeError('Bitrix24 connector is not configured for live OAuth')
        self._auth.exchange_code(
            secret_ref=secret_ref,
            authorization_code=authorization_code,
            redirect_uri=redirect_uri,
        )

    def revoke_oauth_binding(self, *, secret_ref: str) -> None:
        if self._auth is not None:
            self._auth.revoke_binding(secret_ref=secret_ref)

    @staticmethod
    def _live_requested(connection: CrmConnectionRef) -> bool:
        return bool(connection.metadata.get('live_api'))

    def _live_client(self, connection: CrmConnectionRef) -> Bitrix24Client:
        if self._auth is None:
            raise RuntimeError('Bitrix24 live OAuth is not configured')
        if not connection.secret_ref:
            raise RuntimeError('Bitrix24 live connection is missing secret_ref')
        return self._auth.authorized_client(secret_ref=connection.secret_ref)

    def verify_connection(self, connection: CrmConnectionRef) -> dict[str, object]:
        if not self._live_requested(connection):
            return self._store.verify_connection(connection)
        try:
            self._live_client(connection).probe_crm()
        except (RuntimeError, ValueError) as exc:
            return {
                'verified': False,
                'provider_key': 'bitrix24',
                'reason': str(exc),
                'live_api': True,
            }
        return {
            'verified': True,
            'provider_key': 'bitrix24',
            'reason': 'verified',
            'live_api': True,
        }

    def list_pipelines(self, connection: CrmConnectionRef):
        if not self._live_requested(connection):
            return self._store.list_pipelines(connection)
        client = self._live_client(connection)
        pipelines: list[CrmPipeline] = []
        for category in client.list_categories():
            raw_id = category.get('id')
            try:
                category_id = int(raw_id)
            except (TypeError, ValueError):
                continue
            stages: list[CrmStage] = []
            for index, row in enumerate(client.list_stages(category_id)):
                stage_id = str(row.get('STATUS_ID') or '').strip()
                if not stage_id:
                    continue
                semantics = str(row.get('SEMANTICS') or '').strip().upper()
                extra = row.get('EXTRA')
                semantic_word = str(extra.get('SEMANTICS') or '').strip().casefold() if isinstance(extra, Mapping) else ''
                is_won = semantics == 'S' or semantic_word == 'success'
                is_lost = semantics == 'F' or semantic_word in {'failure', 'apology'}
                sort_value = row.get('SORT')
                try:
                    order_index = int(sort_value)
                except (TypeError, ValueError):
                    order_index = index
                stages.append(
                    CrmStage(
                        stage_key=stage_id,
                        display_name=str(row.get('NAME') or stage_id),
                        order_index=order_index,
                        is_closed=is_won or is_lost,
                        is_won=is_won,
                    )
                )
            pipeline_id = str(category_id)
            pipelines.append(
                CrmPipeline(
                    pipeline_key=pipeline_id,
                    display_name=str(category.get('name') or pipeline_id),
                    stages=tuple(stages),
                    external_id=pipeline_id,
                )
            )
        return tuple(pipelines)

    def upsert_pipeline(
        self,
        connection: CrmConnectionRef,
        pipeline: CrmPipeline,
        *,
        idempotency_key: str,
    ) -> dict[str, object]:
        if self._live_requested(connection):
            raise NotImplementedError('Bitrix24 live pipeline writes are not implemented')
        return self._store.upsert_pipeline(connection, pipeline, idempotency_key=idempotency_key)

    @staticmethod
    def _provider_record_id(value: object, *, label: str) -> str | None:
        text = str(value or '').strip()
        if not text:
            return None
        if not text.isdigit() or int(text) <= 0:
            raise ValueError(f'Bitrix24 {label} provider record ID must be numeric')
        return text

    @staticmethod
    def _split_name(full_name: str | None, fallback: str) -> tuple[str, str | None]:
        parts = [part for part in str(full_name or '').split() if part]
        if not parts:
            return fallback, None
        return parts[0], ' '.join(parts[1:]) or None

    @classmethod
    def _contact_base_fields(cls, contact: CrmContact) -> dict[str, object]:
        first_name, last_name = cls._split_name(contact.full_name, contact.contact_id)
        fields: dict[str, object] = {'name': first_name}
        if last_name:
            fields['lastName'] = last_name
        if contact.owner_id:
            if not str(contact.owner_id).isdigit():
                raise ValueError('Bitrix24 contact owner_id must be numeric')
            fields['assignedById'] = int(str(contact.owner_id))
        for key, value in contact.custom_fields.items():
            if str(key).startswith('ufCrm'):
                fields[str(key)] = value
        return fields

    @staticmethod
    def _desired_contact_multifields(contact: CrmContact) -> tuple[tuple[str, str], ...]:
        values: list[tuple[str, str]] = []
        if contact.identity.phone:
            values.append(('PHONE', contact.identity.phone))
        if contact.identity.email:
            values.append(('EMAIL', contact.identity.email))
        return tuple(values)

    @classmethod
    def _contact_create_fields(cls, contact: CrmContact) -> dict[str, object]:
        fields = cls._contact_base_fields(contact)
        fm = [
            {'typeId': kind, 'valueType': 'WORK', 'value': value}
            for kind, value in cls._desired_contact_multifields(contact)
        ]
        if fm:
            fields['fm'] = fm
        return fields

    @staticmethod
    def _existing_multifield_rows(record: Mapping[str, object]) -> tuple[dict[str, object], ...]:
        raw = record.get('fm')
        rows: list[dict[str, object]] = []
        if isinstance(raw, Mapping):
            for raw_key, raw_value in raw.items():
                if not isinstance(raw_value, Mapping):
                    continue
                item = dict(raw_value)
                if item.get('id') is None and str(raw_key).isdigit():
                    item['id'] = str(raw_key)
                rows.append(item)
        elif isinstance(raw, list):
            rows.extend(dict(item) for item in raw if isinstance(item, Mapping))
        return tuple(rows)

    @classmethod
    def _contact_update_fields(
        cls,
        contact: CrmContact,
        existing_record: Mapping[str, object],
    ) -> dict[str, object]:
        fields = cls._contact_base_fields(contact)
        desired = cls._desired_contact_multifields(contact)
        if not desired:
            return fields

        existing_rows = cls._existing_multifield_rows(existing_record)
        fm: dict[str, dict[str, str]] = {}
        next_new = 0
        for kind, value in desired:
            candidates = [
                item
                for item in existing_rows
                if str(item.get('typeId') or '').strip().upper() == kind
            ]
            preferred = next(
                (
                    item
                    for item in candidates
                    if str(item.get('valueType') or '').strip().upper() == 'WORK'
                ),
                candidates[0] if candidates else None,
            )
            raw_id = preferred.get('id') if preferred is not None else None
            record_key = str(raw_id or '').strip()
            if not record_key.isdigit() or int(record_key) <= 0:
                record_key = f'n{next_new}'
                next_new += 1
            value_type = (
                str(preferred.get('valueType') or 'WORK').strip().upper()
                if preferred is not None
                else 'WORK'
            )
            fm[record_key] = {
                'typeId': kind,
                'valueType': value_type or 'WORK',
                'value': value,
            }
        fields['fm'] = fm
        return fields

    def upsert_contact(
        self,
        connection: CrmConnectionRef,
        contact: CrmContact,
        *,
        idempotency_key: str,
    ) -> dict[str, object]:
        dedup_key = contact.identity.canonical_key or contact.contact_id
        if not self._live_requested(connection):
            return self._store.upsert_contact(
                connection,
                {
                    'contact_id': contact.contact_id,
                    'full_name': contact.full_name,
                    'email': contact.identity.email,
                    'phone': contact.identity.phone,
                    'owner_id': contact.owner_id,
                    'custom_fields': dict(contact.custom_fields),
                },
                dedup_key=dedup_key,
                idempotency_key=idempotency_key,
            )
        client = self._live_client(connection)
        provider_id = self._provider_record_id(
            contact.identity.external_ids.get('bitrix24'),
            label='contact',
        )
        if provider_id:
            existing_record = client.get_item(
                entity_type_id=self.CONTACT_ENTITY_TYPE_ID,
                record_id=provider_id,
            )
            if existing_record is None:
                raise RuntimeError('Bitrix24 contact provider record ID does not exist')
            fields = self._contact_update_fields(contact, existing_record)
            client.update_item(
                entity_type_id=self.CONTACT_ENTITY_TYPE_ID,
                record_id=provider_id,
                fields=fields,
            )
            operation = 'update'
            record_id = provider_id
        else:
            fields = self._contact_create_fields(contact)
            created = client.create_item(entity_type_id=self.CONTACT_ENTITY_TYPE_ID, fields=fields)
            record_id = str(created.get('id') or '').strip()
            if not record_id.isdigit():
                raise RuntimeError('Bitrix24 contact create did not return an ID')
            operation = 'create'
        if client.get_item(entity_type_id=self.CONTACT_ENTITY_TYPE_ID, record_id=record_id) is None:
            raise RuntimeError('Bitrix24 contact write could not be verified by readback')
        return {
            'operation': operation,
            'record_id': record_id,
            'dedup_key': dedup_key,
            'idempotency_key': idempotency_key,
        }

    @staticmethod
    def _mapped_pipeline_id(connection: CrmConnectionRef, pipeline_key: str) -> int:
        mapping = connection.metadata.get('pipeline_id_map')
        raw = mapping.get(pipeline_key) if isinstance(mapping, Mapping) else pipeline_key
        text = '' if raw is None else str(raw).strip()
        if not text.isdigit():
            raise ValueError('Bitrix24 deal pipeline mapping must resolve to a numeric category ID')
        return int(text)

    @staticmethod
    def _mapped_stage_id(connection: CrmConnectionRef, stage_key: str) -> str:
        mapping = connection.metadata.get('stage_id_map')
        raw = mapping.get(stage_key) if isinstance(mapping, Mapping) else stage_key
        text = str(raw or '').strip()
        if not text:
            raise ValueError('Bitrix24 deal stage mapping must resolve to a provider stage ID')
        return text

    def _deal_fields(self, connection: CrmConnectionRef, deal: CrmDeal) -> dict[str, object]:
        fields: dict[str, object] = {
            'title': deal.title,
            'categoryId': self._mapped_pipeline_id(connection, deal.pipeline_key),
            'stageId': self._mapped_stage_id(connection, deal.stage_key),
        }
        if deal.value is not None:
            if not isinstance(deal.value, Decimal) or not deal.value.is_finite():
                raise ValueError('Bitrix24 deal value must be a finite Decimal')
            fields['isManualOpportunity'] = True
            fields['opportunity'] = float(deal.value)
        if deal.currency:
            fields['currencyId'] = deal.currency
        if deal.owner_id:
            if not str(deal.owner_id).isdigit():
                raise ValueError('Bitrix24 deal owner_id must be numeric')
            fields['assignedById'] = int(str(deal.owner_id))
        contact_record_id = self._provider_record_id(
            deal.custom_fields.get('bitrix24_contact_record_id'),
            label='linked contact',
        )
        if contact_record_id:
            fields['contactId'] = int(contact_record_id)
        for key, value in deal.custom_fields.items():
            if str(key).startswith('ufCrm'):
                fields[str(key)] = value
        return fields

    def upsert_deal(
        self,
        connection: CrmConnectionRef,
        deal: CrmDeal,
        *,
        idempotency_key: str,
    ) -> dict[str, object]:
        dedup_key = str(deal.deal_id or '').strip()
        if not dedup_key:
            raise ValueError('Bitrix24 deal_id must not be blank')
        if not self._live_requested(connection):
            return self._store.upsert_deal(
                connection,
                {
                    'deal_id': deal.deal_id,
                    'title': deal.title,
                    'pipeline_key': deal.pipeline_key,
                    'stage_key': deal.stage_key,
                    'value': deal.value,
                    'currency': deal.currency,
                    'owner_id': deal.owner_id,
                    'contact_id': deal.contact_id,
                    'custom_fields': dict(deal.custom_fields),
                },
                dedup_key=dedup_key,
                idempotency_key=idempotency_key,
            )
        client = self._live_client(connection)
        fields = self._deal_fields(connection, deal)
        provider_id = self._provider_record_id(
            deal.custom_fields.get('bitrix24_record_id'),
            label='deal',
        )
        if provider_id:
            if client.get_item(entity_type_id=self.DEAL_ENTITY_TYPE_ID, record_id=provider_id) is None:
                raise RuntimeError('Bitrix24 deal provider record ID does not exist')
            client.update_item(
                entity_type_id=self.DEAL_ENTITY_TYPE_ID,
                record_id=provider_id,
                fields=fields,
            )
            operation = 'update'
            record_id = provider_id
        else:
            created = client.create_item(entity_type_id=self.DEAL_ENTITY_TYPE_ID, fields=fields)
            record_id = str(created.get('id') or '').strip()
            if not record_id.isdigit():
                raise RuntimeError('Bitrix24 deal create did not return an ID')
            operation = 'create'
        if client.get_item(entity_type_id=self.DEAL_ENTITY_TYPE_ID, record_id=record_id) is None:
            raise RuntimeError('Bitrix24 deal write could not be verified by readback')
        return {
            'operation': operation,
            'record_id': record_id,
            'dedup_key': dedup_key,
            'idempotency_key': idempotency_key,
        }

    def append_note(
        self,
        connection: CrmConnectionRef,
        note: CrmNote,
        *,
        idempotency_key: str,
    ) -> dict[str, object]:
        if not self._live_requested(connection):
            return self._store.append_note(
                connection,
                {
                    'body': note.body,
                    'linked_object_type': note.linked_object_type,
                    'linked_object_id': note.linked_object_id,
                },
                idempotency_key=idempotency_key,
            )
        entity_map = {
            'contact': 'contact',
            'contacts': 'contact',
            'deal': 'deal',
            'deals': 'deal',
        }
        entity_type = entity_map.get(note.linked_object_type.strip().casefold())
        if entity_type is None:
            raise ValueError('Bitrix24 live note requires a contact or deal entity type')
        record_id = self._live_client(connection).append_timeline_comment(
            entity_type=entity_type,
            entity_id=note.linked_object_id,
            text=note.body,
        )
        return {
            'operation': 'append',
            'record_id': record_id,
            'idempotency_key': idempotency_key,
        }

    @classmethod
    def _contact_verification_view(cls, record: Mapping[str, object]) -> dict[str, object]:
        view = dict(record)
        names = [
            str(record.get('name') or '').strip(),
            str(record.get('secondName') or '').strip(),
            str(record.get('lastName') or '').strip(),
        ]
        view['full_name'] = ' '.join(part for part in names if part) or None
        for item in cls._existing_multifield_rows(record):
            kind = str(item.get('typeId') or '').strip().upper()
            value = str(item.get('value') or '').strip()
            if kind == 'EMAIL' and value and not str(view.get('email') or '').strip():
                view['email'] = value
            elif kind == 'PHONE' and value and not str(view.get('phone') or '').strip():
                view['phone'] = value
        return view

    @staticmethod
    def _reverse_map(connection: CrmConnectionRef, *, key: str, value: object) -> str | None:
        text = '' if value is None else str(value).strip()
        mapping = connection.metadata.get(key)
        if isinstance(mapping, Mapping):
            for canonical, provider in mapping.items():
                if str(provider).strip() == text:
                    return str(canonical)
        return text or None

    @classmethod
    def _deal_verification_view(
        cls,
        connection: CrmConnectionRef,
        record: Mapping[str, object],
    ) -> dict[str, object]:
        view = dict(record)
        view['title'] = str(record.get('title') or '').strip() or None
        view['pipeline_key'] = cls._reverse_map(
            connection,
            key='pipeline_id_map',
            value=record.get('categoryId'),
        )
        view['stage_key'] = cls._reverse_map(
            connection,
            key='stage_id_map',
            value=record.get('stageId'),
        )
        value = record.get('opportunity')
        if value is not None:
            try:
                view['value'] = Decimal(str(value))
            except (InvalidOperation, ValueError):
                view['value'] = value
        return view

    def verify_write(
        self,
        connection: CrmConnectionRef,
        request: CrmVerificationRequest,
    ) -> CrmVerificationResult:
        if not self._live_requested(connection):
            record = self._store.get_record(
                connection,
                entity_type=request.entity_type,
                record_id=request.record_id,
            )
        else:
            record_id = str(request.record_id or '').strip()
            if not record_id:
                return CrmVerificationResult(
                    verified=False,
                    provider_key='bitrix24',
                    entity_type=request.entity_type,
                    record_id=request.record_id,
                    reason='record_id_missing',
                    evidence={},
                )
            try:
                client = self._live_client(connection)
                if request.entity_type == 'contact':
                    raw = client.get_item(entity_type_id=self.CONTACT_ENTITY_TYPE_ID, record_id=record_id)
                    record = self._contact_verification_view(raw) if raw is not None else None
                elif request.entity_type == 'deal':
                    raw = client.get_item(entity_type_id=self.DEAL_ENTITY_TYPE_ID, record_id=record_id)
                    record = self._deal_verification_view(connection, raw) if raw is not None else None
                else:
                    record = None
            except (RuntimeError, ValueError) as exc:
                return CrmVerificationResult(
                    verified=False,
                    provider_key='bitrix24',
                    entity_type=request.entity_type,
                    record_id=request.record_id,
                    reason=str(exc),
                    evidence={},
                )
        if record is None:
            return CrmVerificationResult(
                verified=False,
                provider_key='bitrix24',
                entity_type=request.entity_type,
                record_id=request.record_id,
                reason='record_not_found',
                evidence={},
            )
        mismatches = {
            key: {'expected': expected, 'actual': record.get(key)}
            for key, expected in request.expected_fields.items()
            if expected is not None and record.get(key) != expected
        }
        return CrmVerificationResult(
            verified=not mismatches,
            provider_key='bitrix24',
            entity_type=request.entity_type,
            record_id=request.record_id,
            reason='provider_readback_match' if not mismatches else 'field_mismatch',
            evidence={'record': record, 'mismatches': mismatches},
        )

    def build_snapshot(self, connection: CrmConnectionRef) -> dict[str, object]:
        if not self._live_requested(connection):
            return self._store.build_snapshot(connection)
        try:
            pipelines = self.list_pipelines(connection)
        except (RuntimeError, ValueError) as exc:
            return {
                'provider_key': 'bitrix24',
                'live_api': True,
                'snapshot_available': False,
                'reason': str(exc),
            }
        return {
            'provider_key': 'bitrix24',
            'live_api': True,
            'snapshot_available': True,
            'pipeline_count': len(pipelines),
            'contact_count': None,
            'deal_count': None,
            'recent_activity': (),
        }
