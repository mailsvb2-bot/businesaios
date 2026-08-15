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
from crm.providers.amocrm.amocrm_api_config import AmoCrmApiConfig
from crm.providers.amocrm.amocrm_auth_adapter import AmoCrmAuthAdapter
from crm.providers.amocrm.amocrm_capability_descriptor import build_amocrm_capability_descriptor
from crm.providers.amocrm.amocrm_client import AmoCrmClient
from crm.providers.common.crm_oauth_token_store import CrmOAuthTokenStore, InMemoryCrmOAuthTokenStore
from crm.providers.common.crm_provider_store import CrmProviderStore


class AmoCrmConnector(CrmConnector):
    def __init__(
        self,
        *,
        token_store: CrmOAuthTokenStore | None = None,
        client_id: str | None = None,
        client_secret: str | None = None,
        api_config: AmoCrmApiConfig | None = None,
    ) -> None:
        self.provider = CrmProvider(
            provider_key='amocrm',
            display_name='amoCRM',
            capability_descriptor=build_amocrm_capability_descriptor(),
        )
        self._store = CrmProviderStore('amocrm')
        self._config = api_config or AmoCrmApiConfig()
        self._contact_field_id_cache: dict[str, dict[str, int]] = {}
        self._auth: AmoCrmAuthAdapter | None = None
        if client_id and client_secret:
            self._auth = AmoCrmAuthAdapter(
                token_store=token_store or InMemoryCrmOAuthTokenStore(),
                client_id=client_id,
                client_secret=client_secret,
                api_config=self._config,
            )

    def capabilities(self):
        return self.provider.capability_descriptor

    def supports_live_api(self) -> bool:
        return self._auth is not None

    def exchange_oauth_code_with_metadata(
        self,
        *,
        secret_ref: str,
        authorization_code: str,
        redirect_uri: str,
        callback_metadata: Mapping[str, object],
    ) -> None:
        if self._auth is None:
            raise RuntimeError('amoCRM connector is not configured for live OAuth')
        self._auth.exchange_code_with_metadata(
            secret_ref=secret_ref,
            authorization_code=authorization_code,
            redirect_uri=redirect_uri,
            callback_metadata=callback_metadata,
        )

    def exchange_oauth_code(self, *, secret_ref: str, authorization_code: str, redirect_uri: str) -> None:
        raise RuntimeError('amoCRM OAuth callback requires account metadata')

    def revoke_oauth_binding(self, *, secret_ref: str) -> None:
        if self._auth is not None:
            self._auth.revoke_binding(secret_ref=secret_ref)

    @staticmethod
    def _live_requested(connection: CrmConnectionRef) -> bool:
        return bool(connection.metadata.get('live_api'))

    def _live_client(self, connection: CrmConnectionRef) -> AmoCrmClient:
        if self._auth is None:
            raise RuntimeError('amoCRM live OAuth is not configured')
        if not connection.secret_ref:
            raise RuntimeError('amoCRM live connection is missing secret_ref')
        return self._auth.authorized_client(secret_ref=connection.secret_ref)

    def verify_connection(self, connection: CrmConnectionRef) -> dict[str, object]:
        if not self._live_requested(connection):
            return self._store.verify_connection(connection)
        try:
            account = self._live_client(connection).account_info()
        except (RuntimeError, ValueError) as exc:
            return {'verified': False, 'provider_key': 'amocrm', 'reason': str(exc), 'live_api': True}
        account_id = str(account.get('id') or '').strip()
        return {
            'verified': bool(account_id),
            'provider_key': 'amocrm',
            'reason': 'verified' if account_id else 'account_id_missing',
            'external_account_id': account_id or None,
            'live_api': True,
        }

    def list_pipelines(self, connection: CrmConnectionRef):
        if not self._live_requested(connection):
            return self._store.list_pipelines(connection)
        pipelines: list[CrmPipeline] = []
        for row in self._live_client(connection).list_pipelines():
            pipeline_id = str(row.get('id') or '').strip()
            embedded = row.get('_embedded')
            status_rows = embedded.get('statuses') if isinstance(embedded, Mapping) else None
            stages: list[CrmStage] = []
            if isinstance(status_rows, list):
                for index, status in enumerate(status_rows):
                    if not isinstance(status, Mapping):
                        continue
                    status_id = str(status.get('id') or '').strip()
                    if not status_id:
                        continue
                    stages.append(
                        CrmStage(
                            stage_key=status_id,
                            display_name=str(status.get('name') or status_id),
                            order_index=int(status.get('sort') or index),
                            is_closed=status_id in {'142', '143'},
                            is_won=status_id == '142',
                        )
                    )
            if pipeline_id:
                pipelines.append(
                    CrmPipeline(
                        pipeline_key=pipeline_id,
                        display_name=str(row.get('name') or pipeline_id),
                        stages=tuple(stages),
                        external_id=pipeline_id,
                        metadata={'is_main': bool(row.get('is_main'))},
                    )
                )
        return tuple(pipelines)

    def upsert_pipeline(
        self, connection: CrmConnectionRef, pipeline: CrmPipeline, *, idempotency_key: str
    ) -> dict[str, object]:
        if self._live_requested(connection):
            raise NotImplementedError('amoCRM live pipeline writes are not implemented')
        return self._store.upsert_pipeline(connection, pipeline, idempotency_key=idempotency_key)

    @staticmethod
    def _phone_key(value: str | None) -> str:
        return ''.join(char for char in str(value or '') if char.isdigit())

    @classmethod
    def _contact_matches(cls, row: Mapping[str, object], contact: CrmContact) -> bool:
        wanted_email = str(contact.identity.email or '').strip().casefold()
        wanted_phone = cls._phone_key(contact.identity.phone)
        if not wanted_email and not wanted_phone:
            return False
        values = row.get('custom_fields_values')
        if not isinstance(values, list):
            return False
        emails: set[str] = set()
        phones: set[str] = set()
        for field in values:
            if not isinstance(field, Mapping):
                continue
            code = str(field.get('field_code') or '').upper()
            field_values = field.get('values')
            if not isinstance(field_values, list):
                continue
            for item in field_values:
                if not isinstance(item, Mapping):
                    continue
                value = str(item.get('value') or '').strip()
                if code == 'EMAIL' and value:
                    emails.add(value.casefold())
                if code == 'PHONE' and value:
                    phones.add(cls._phone_key(value))
        return bool((wanted_email and wanted_email in emails) or (wanted_phone and wanted_phone in phones))

    def _contact_field_ids(
        self, connection: CrmConnectionRef, client: AmoCrmClient
    ) -> dict[str, int]:
        cache_key = str(connection.secret_ref or connection.connection_id)
        cached = self._contact_field_id_cache.get(cache_key)
        if cached is not None:
            return dict(cached)
        resolved: dict[str, int] = {}
        for field in client.list_contact_custom_fields():
            code = str(field.get('code') or '').strip().upper()
            raw_id = field.get('id')
            if (
                code in {'PHONE', 'EMAIL'}
                and isinstance(raw_id, int)
                and not isinstance(raw_id, bool)
                and raw_id > 0
            ):
                resolved[code] = raw_id
        if {'PHONE', 'EMAIL'} <= set(resolved):
            self._contact_field_id_cache[cache_key] = dict(resolved)
        return resolved

    def _contact_fields(
        self, connection: CrmConnectionRef, client: AmoCrmClient, contact: CrmContact
    ) -> dict[str, object]:
        fields: dict[str, object] = {'name': contact.full_name or contact.contact_id}
        if contact.owner_id:
            owner_id = str(contact.owner_id).strip()
            if not owner_id.isdigit() or int(owner_id) <= 0:
                raise ValueError('amoCRM contact owner_id must be a positive numeric provider ID')
            fields['responsible_user_id'] = int(owner_id)
        custom_fields: list[dict[str, object]] = []
        if contact.identity.phone or contact.identity.email:
            field_ids = self._contact_field_ids(connection, client)
            if contact.identity.phone:
                phone_id = field_ids.get('PHONE')
                if phone_id is None:
                    raise RuntimeError('amoCRM PHONE field could not be resolved')
                custom_fields.append(
                    {
                        'field_id': phone_id,
                        'values': [{'value': contact.identity.phone, 'enum_code': 'WORK'}],
                    }
                )
            if contact.identity.email:
                email_id = field_ids.get('EMAIL')
                if email_id is None:
                    raise RuntimeError('amoCRM EMAIL field could not be resolved')
                custom_fields.append(
                    {
                        'field_id': email_id,
                        'values': [{'value': contact.identity.email, 'enum_code': 'WORK'}],
                    }
                )
        if custom_fields:
            fields['custom_fields_values'] = custom_fields
        return fields

    def upsert_contact(
        self, connection: CrmConnectionRef, contact: CrmContact, *, idempotency_key: str
    ) -> dict[str, object]:
        dedup_key = str(contact.identity.canonical_key or '').strip() or str(contact.contact_id or '').strip()
        if not dedup_key:
            raise ValueError('amoCRM contact requires canonical_key or contact_id')
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
        fields = self._contact_fields(connection, client, contact)
        existing_id: str | None = None
        provider_id = str(contact.identity.external_ids.get('amocrm') or '').strip()
        if provider_id:
            if not provider_id.isdigit():
                raise ValueError('amoCRM contact external ID must be numeric')
            existing = client.get_contact(provider_id)
            if existing is None:
                raise RuntimeError('amoCRM contact external ID does not exist')
            existing_id = provider_id
        else:
            query = str(contact.identity.email or contact.identity.phone or '').strip()
            matches = [
                row
                for row in client.search_contacts(query)
                if self._contact_matches(row, contact)
            ] if query else []
            if len(matches) > 1:
                raise RuntimeError('amoCRM contact identity is ambiguous')
            if matches:
                existing_id = str(matches[0].get('id') or '').strip() or None
        if existing_id:
            client.update_contact(existing_id, fields)
            operation = 'update'
            record_id = existing_id
        else:
            created = client.create_contact(fields)
            record_id = str(created.get('id') or '').strip()
            if not record_id:
                raise RuntimeError('amoCRM contact create did not return an id')
            operation = 'create'
        readback = client.get_contact(record_id)
        if readback is None:
            raise RuntimeError('amoCRM contact write could not be verified by readback')
        return {
            'operation': operation,
            'record_id': record_id,
            'dedup_key': dedup_key,
            'idempotency_key': idempotency_key,
        }

    @staticmethod
    def _mapped_id(connection: CrmConnectionRef, *, map_key: str, canonical_key: str) -> int:
        key = str(canonical_key or '').strip()
        if key.isdigit():
            value = int(key)
            if value > 0:
                return value
            raise ValueError(f'amoCRM {map_key} provider ID must be positive')
        mapping = connection.metadata.get(map_key)
        value = mapping.get(key) if isinstance(mapping, Mapping) else None
        if isinstance(value, int) and not isinstance(value, bool) and value > 0:
            return value
        if isinstance(value, str) and value.strip().isdigit() and int(value.strip()) > 0:
            return int(value.strip())
        raise ValueError(f'amoCRM {map_key} has no provider ID for {key!r}')

    @classmethod
    def _deal_fields(cls, connection: CrmConnectionRef, deal: CrmDeal) -> dict[str, object]:
        fields: dict[str, object] = {
            'name': deal.title,
            'pipeline_id': cls._mapped_id(connection, map_key='pipeline_id_map', canonical_key=deal.pipeline_key),
            'status_id': cls._mapped_id(connection, map_key='status_id_map', canonical_key=deal.stage_key),
        }
        if deal.value is not None:
            if not deal.value.is_finite():
                raise ValueError('amoCRM lead price must be finite')
            if deal.value != deal.value.to_integral_value():
                raise ValueError('amoCRM lead price cannot represent fractional values without loss')
            fields['price'] = int(deal.value)
        if deal.currency:
            account_currency = str(connection.metadata.get('account_currency') or '').strip().upper()
            if not account_currency or account_currency != deal.currency.strip().upper():
                raise ValueError('amoCRM deal currency must match configured account_currency')
        if deal.owner_id:
            owner_id = str(deal.owner_id).strip()
            if not owner_id.isdigit() or int(owner_id) <= 0:
                raise ValueError('amoCRM deal owner_id must be a positive numeric provider ID')
            fields['responsible_user_id'] = int(owner_id)
        return fields

    @staticmethod
    def _linked_contact_provider_id(deal: CrmDeal) -> str | None:
        contact_record_id = str(deal.custom_fields.get('amocrm_contact_record_id') or '').strip()
        if not contact_record_id:
            return None
        if not contact_record_id.isdigit() or int(contact_record_id) <= 0:
            raise ValueError('amoCRM linked contact provider record ID must be a positive integer')
        return contact_record_id

    def upsert_deal(
        self, connection: CrmConnectionRef, deal: CrmDeal, *, idempotency_key: str
    ) -> dict[str, object]:
        dedup_key = str(deal.deal_id or '').strip()
        if not dedup_key:
            raise ValueError('amoCRM deal_id must not be blank')
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
        provider_id = str(deal.custom_fields.get('amocrm_record_id') or '').strip()
        if provider_id:
            if not provider_id.isdigit():
                raise ValueError('amoCRM lead provider record ID must be numeric')
            if client.get_lead(provider_id) is None:
                raise RuntimeError('amoCRM lead provider record ID does not exist')
            client.update_lead(provider_id, fields)
            operation = 'update'
            record_id = provider_id
        else:
            created = client.create_lead(fields)
            record_id = str(created.get('id') or '').strip()
            if not record_id:
                raise RuntimeError('amoCRM lead create did not return an id')
            operation = 'create'
        contact_record_id = self._linked_contact_provider_id(deal)
        if contact_record_id is not None:
            client.link_contact_to_lead(
                lead_id=record_id,
                contact_id=contact_record_id,
                is_main=True,
            )
        if client.get_lead(record_id) is None:
            raise RuntimeError('amoCRM lead write could not be verified by readback')
        return {
            'operation': operation,
            'record_id': record_id,
            'dedup_key': dedup_key,
            'idempotency_key': idempotency_key,
        }

    def append_note(
        self, connection: CrmConnectionRef, note: CrmNote, *, idempotency_key: str
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
        entity_map = {'contact': 'contacts', 'contacts': 'contacts', 'deal': 'leads', 'lead': 'leads', 'leads': 'leads'}
        entity_type = entity_map.get(note.linked_object_type.strip().casefold())
        if entity_type is None or not note.linked_object_id.strip().isdigit():
            raise ValueError('amoCRM live note requires a supported entity type and numeric provider record id')
        created = self._live_client(connection).append_common_note(
            entity_type=entity_type,
            entity_id=note.linked_object_id.strip(),
            text=note.body,
        )
        record_id = str(created.get('id') or '').strip()
        if not record_id:
            raise RuntimeError('amoCRM note create did not return an id')
        return {'operation': 'append', 'record_id': record_id, 'idempotency_key': idempotency_key}

    @classmethod
    def _contact_verification_view(cls, record: Mapping[str, object]) -> dict[str, object]:
        view = dict(record)
        view['full_name'] = str(record.get('name') or '').strip() or None
        values = record.get('custom_fields_values')
        if isinstance(values, list):
            for field in values:
                if not isinstance(field, Mapping):
                    continue
                code = str(field.get('field_code') or '').strip().upper()
                field_values = field.get('values')
                if code not in {'EMAIL', 'PHONE'} or not isinstance(field_values, list):
                    continue
                first_value = next(
                    (
                        str(item.get('value') or '').strip()
                        for item in field_values
                        if isinstance(item, Mapping) and str(item.get('value') or '').strip()
                    ),
                    '',
                )
                if code == 'EMAIL':
                    view['email'] = first_value or None
                else:
                    view['phone'] = first_value or None
        return view

    @staticmethod
    def _reverse_mapped_id(
        connection: CrmConnectionRef, *, map_key: str, provider_id: object
    ) -> str | None:
        if provider_id is None:
            return None
        provider_text = str(provider_id).strip()
        mapping = connection.metadata.get(map_key)
        if isinstance(mapping, Mapping):
            for canonical_key, mapped in mapping.items():
                if str(mapped).strip() == provider_text:
                    return str(canonical_key)
        return provider_text or None

    @classmethod
    def _deal_verification_view(
        cls, connection: CrmConnectionRef, record: Mapping[str, object]
    ) -> dict[str, object]:
        view = dict(record)
        view['title'] = str(record.get('name') or '').strip() or None
        view['stage_key'] = cls._reverse_mapped_id(
            connection, map_key='status_id_map', provider_id=record.get('status_id')
        )
        view['pipeline_key'] = cls._reverse_mapped_id(
            connection, map_key='pipeline_id_map', provider_id=record.get('pipeline_id')
        )
        price = record.get('price')
        if isinstance(price, (int, str)) and not isinstance(price, bool):
            try:
                view['value'] = Decimal(str(price))
            except (InvalidOperation, ValueError):
                view['value'] = price
        return view

    def verify_write(
        self, connection: CrmConnectionRef, request: CrmVerificationRequest
    ) -> CrmVerificationResult:
        if not self._live_requested(connection):
            record = self._store.get_record(
                connection, entity_type=request.entity_type, record_id=request.record_id
            )
        else:
            if not str(request.record_id or '').strip():
                return CrmVerificationResult(
                    verified=False,
                    provider_key='amocrm',
                    entity_type=request.entity_type,
                    record_id=request.record_id,
                    reason='record_id_missing',
                    evidence={},
                )
            try:
                client = self._live_client(connection)
            except (RuntimeError, ValueError) as exc:
                return CrmVerificationResult(
                    verified=False,
                    provider_key='amocrm',
                    entity_type=request.entity_type,
                    record_id=request.record_id,
                    reason=str(exc),
                    evidence={},
                )
            if request.entity_type == 'contact':
                raw_record = client.get_contact(str(request.record_id or ''))
                record = (
                    self._contact_verification_view(raw_record)
                    if raw_record is not None
                    else None
                )
            elif request.entity_type in {'deal', 'lead'}:
                raw_record = client.get_lead(str(request.record_id or ''))
                record = (
                    self._deal_verification_view(connection, raw_record)
                    if raw_record is not None
                    else None
                )
            else:
                record = None
        if record is None:
            return CrmVerificationResult(
                verified=False,
                provider_key='amocrm',
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
            provider_key='amocrm',
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
                'provider_key': 'amocrm',
                'live_api': True,
                'snapshot_available': False,
                'reason': str(exc),
            }
        return {
            'provider_key': 'amocrm',
            'live_api': True,
            'snapshot_available': True,
            'pipeline_count': len(pipelines),
            'contact_count': None,
            'deal_count': None,
            'recent_activity': (),
        }
