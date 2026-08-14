from __future__ import annotations

from collections.abc import Mapping as MappingABC
from decimal import Decimal

from crm.crm_connection_contract import CrmConnectionRef
from crm.crm_connector_contract import CrmConnector
from crm.crm_contact_contract import CrmContact
from crm.crm_deal_contract import CrmDeal
from crm.crm_note_contract import CrmNote
from crm.crm_pipeline_contract import CrmPipeline
from crm.crm_provider_contract import CrmProvider
from crm.crm_verification_contract import CrmVerificationRequest, CrmVerificationResult
from crm.providers.common.crm_oauth_token_store import CrmOAuthTokenStore, InMemoryCrmOAuthTokenStore
from crm.providers.common.crm_provider_store import CrmProviderStore
from crm.providers.salesforce.salesforce_api_config import SalesforceApiConfig
from crm.providers.salesforce.salesforce_capability_descriptor import build_salesforce_capability_descriptor
from crm.providers.salesforce.salesforce_client import SalesforceClient


class SalesforceConnector(CrmConnector):
    """Salesforce adapter for the canonical CRM contract.

    Live network calls are delegated to ``SalesforceClient``, which itself uses
    the canonical CRM HTTP client/runtime effects boundary. ``live_api=True`` is
    fail-closed: missing live credentials never fall back to the hermetic store.
    """

    def __init__(
        self,
        *,
        token_store: CrmOAuthTokenStore | None = None,
        api_config: SalesforceApiConfig | None = None,
    ) -> None:
        self.provider = CrmProvider(
            provider_key="salesforce",
            display_name="Salesforce",
            capability_descriptor=build_salesforce_capability_descriptor(),
        )
        self._store = CrmProviderStore("salesforce")
        self._tokens = token_store or InMemoryCrmOAuthTokenStore()
        self._config = api_config or SalesforceApiConfig()

    def capabilities(self):
        return self.provider.capability_descriptor

    @staticmethod
    def _live_requested(connection: CrmConnectionRef) -> bool:
        return bool(connection.metadata.get("live_api"))

    def _live_client(self, connection: CrmConnectionRef) -> SalesforceClient:
        if not self._live_requested(connection):
            raise RuntimeError("salesforce_live_api_not_requested")
        if not connection.secret_ref:
            raise RuntimeError("salesforce_live_missing_secret_ref")
        token = self._tokens.load(provider_key="salesforce", secret_ref=connection.secret_ref)
        if token is None or not token.access_token.strip():
            raise RuntimeError("salesforce_live_missing_access_token")
        if token.is_expired():
            raise RuntimeError("salesforce_live_access_token_expired")
        instance_url = str(connection.metadata.get("instance_url") or "").strip()
        if not instance_url:
            raise RuntimeError("salesforce_live_missing_instance_url")
        return SalesforceClient(
            access_token=token.access_token,
            instance_url=instance_url,
            config=self._config,
        )

    @staticmethod
    def _contact_external_id(contact: CrmContact) -> str:
        external_id = str(contact.identity.canonical_key or '').strip() or str(contact.contact_id or '').strip()
        if not external_id:
            raise ValueError("Salesforce Contact external ID requires canonical_key or contact_id")
        return external_id

    @staticmethod
    def _external_field(connection: CrmConnectionRef, metadata_key: str) -> str:
        field_name = str(connection.metadata.get(metadata_key) or "BusinessAIOS_Key__c").strip()
        if not field_name:
            raise ValueError(f"Salesforce {metadata_key} must not be blank")
        return field_name

    @staticmethod
    def _salesforce_stage_name(
        connection: CrmConnectionRef,
        deal: CrmDeal,
        custom_fields: dict[str, object],
    ) -> str:
        explicit = str(custom_fields.pop("StageName", "") or "").strip()
        mapping = connection.metadata.get("deal_stage_mapping")
        if isinstance(mapping, MappingABC):
            mapped = str(mapping.get(deal.stage_key) or "").strip()
            if mapped:
                return mapped
        if explicit:
            return explicit
        raise ValueError(
            "Live Salesforce deal upsert requires an explicit StageName: "
            'configure connection.metadata["deal_stage_mapping"] or custom_fields["StageName"]'
        )

    @staticmethod
    def _salesforce_close_date(custom_fields: dict[str, object]) -> object:
        close_date = custom_fields.pop("CloseDate", None)
        if close_date in (None, ""):
            raise ValueError('Live Salesforce deal upsert requires custom_fields["CloseDate"]')
        return close_date

    def verify_connection(self, connection: CrmConnectionRef) -> dict[str, object]:
        if not self._live_requested(connection):
            result = dict(self._store.verify_connection(connection))
            result["live_api"] = False
            return result
        try:
            client = self._live_client(connection)
            client.query("SELECT Id FROM Organization LIMIT 1")
        except (RuntimeError, ValueError) as exc:
            return {
                "verified": False,
                "provider_key": "salesforce",
                "reason": str(exc),
                "live_api": True,
            }
        return {
            "verified": True,
            "provider_key": "salesforce",
            "reason": "verified",
            "live_api": True,
        }

    def list_pipelines(self, connection: CrmConnectionRef):
        # Opportunity stages are org-specific picklists, not portable pipeline objects.
        return ()

    def upsert_pipeline(
        self,
        connection: CrmConnectionRef,
        pipeline: CrmPipeline,
        *,
        idempotency_key: str,
    ) -> dict[str, object]:
        raise NotImplementedError("Salesforce pipeline mutation is intentionally unsupported")

    def upsert_contact(
        self,
        connection: CrmConnectionRef,
        contact: CrmContact,
        *,
        idempotency_key: str,
    ) -> dict[str, object]:
        contact_external_id = self._contact_external_id(contact)
        if not self._live_requested(connection):
            return self._store.upsert_contact(
                connection,
                {
                    "contact_id": contact.contact_id,
                    "full_name": contact.full_name,
                    "email": contact.identity.email,
                    "phone": contact.identity.phone,
                    "custom_fields": dict(contact.custom_fields),
                },
                dedup_key=contact_external_id,
                idempotency_key=idempotency_key,
            )
        client = self._live_client(connection)
        external_field = self._external_field(connection, "contact_external_id_field")
        last_name = str(contact.custom_fields.get("LastName") or contact.full_name or "").strip()
        if not last_name:
            raise ValueError("Live Salesforce Contact upsert requires LastName/full_name")
        fields = {
            str(key): value
            for key, value in contact.custom_fields.items()
            if str(key) != external_field
        }
        fields["LastName"] = last_name
        if contact.identity.email:
            fields["Email"] = contact.identity.email
        if contact.identity.phone:
            fields["Phone"] = contact.identity.phone
        result = client.upsert_external(
            object_name="Contact",
            external_id_field=external_field,
            external_id=contact_external_id,
            fields=fields,
        )
        record = client.get_external(
            object_name="Contact",
            external_id_field=external_field,
            external_id=contact_external_id,
        ) or {}
        record_id = str(result.get("id") or record.get("Id") or contact.contact_id)
        return {
            "operation": self._operation_from_upsert(result),
            "record_id": record_id,
            "dedup_key": contact_external_id,
            "idempotency_key": idempotency_key,
        }

    def upsert_deal(
        self,
        connection: CrmConnectionRef,
        deal: CrmDeal,
        *,
        idempotency_key: str,
    ) -> dict[str, object]:
        if not self._live_requested(connection):
            return self._store.upsert_deal(
                connection,
                {
                    "deal_id": deal.deal_id,
                    "title": deal.title,
                    "pipeline_key": deal.pipeline_key,
                    "stage_key": deal.stage_key,
                    "value": str(deal.value) if deal.value is not None else None,
                    "currency": deal.currency,
                    "custom_fields": dict(deal.custom_fields),
                },
                dedup_key=deal.deal_id,
                idempotency_key=idempotency_key,
            )
        client = self._live_client(connection)
        external_field = self._external_field(connection, "deal_external_id_field")
        custom_fields = {
            str(key): value
            for key, value in deal.custom_fields.items()
            if str(key) != external_field
        }
        stage_name = self._salesforce_stage_name(connection, deal, custom_fields)
        close_date = self._salesforce_close_date(custom_fields)
        fields: dict[str, object] = dict(custom_fields)
        fields.update({"Name": deal.title, "StageName": stage_name, "CloseDate": close_date})
        if deal.value is not None:
            fields["Amount"] = float(Decimal(deal.value))
        if deal.currency and bool(connection.metadata.get("multi_currency_enabled")):
            fields["CurrencyIsoCode"] = deal.currency
        result = client.upsert_external(
            object_name="Opportunity",
            external_id_field=external_field,
            external_id=deal.deal_id,
            fields=fields,
        )
        record = client.get_external(
            object_name="Opportunity",
            external_id_field=external_field,
            external_id=deal.deal_id,
        ) or {}
        record_id = str(result.get("id") or record.get("Id") or deal.deal_id)
        return {
            "operation": self._operation_from_upsert(result),
            "record_id": record_id,
            "dedup_key": deal.deal_id,
            "idempotency_key": idempotency_key,
        }

    def append_note(
        self,
        connection: CrmConnectionRef,
        note: CrmNote,
        *,
        idempotency_key: str,
    ) -> dict[str, object]:
        if self._live_requested(connection):
            raise NotImplementedError(
                "Salesforce live note mutation is unsupported until ContentNote/ContentDocumentLink is verified"
            )
        return self._store.append_note(
            connection,
            {
                "body": note.body,
                "linked_object_type": note.linked_object_type,
                "linked_object_id": note.linked_object_id,
            },
            idempotency_key=idempotency_key,
        )

    @staticmethod
    def _operation_from_upsert(result: MappingABC[str, object]) -> str:
        created = result.get("created")
        if created is True:
            return "create"
        if created is False:
            return "update"
        return "upsert"

    @staticmethod
    def _verification_view(entity_type: str, record: dict[str, object]) -> dict[str, object]:
        view = dict(record)
        if entity_type == "contact":
            view.setdefault("full_name", record.get("Name") or record.get("LastName"))
            view.setdefault("email", record.get("Email"))
            view.setdefault("phone", record.get("Phone"))
        elif entity_type == "deal":
            view.setdefault("title", record.get("Name"))
            view.setdefault("stage_key", record.get("StageName"))
            view.setdefault("value", record.get("Amount"))
            view.setdefault("currency", record.get("CurrencyIsoCode"))
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
            try:
                client = self._live_client(connection)
            except (RuntimeError, ValueError) as exc:
                return CrmVerificationResult(
                    verified=False,
                    provider_key="salesforce",
                    entity_type=request.entity_type,
                    record_id=request.record_id,
                    reason=str(exc),
                    evidence={},
                )
            object_name = {"contact": "Contact", "deal": "Opportunity"}.get(request.entity_type)
            if object_name is None or not request.record_id:
                return CrmVerificationResult(
                    verified=False,
                    provider_key="salesforce",
                    entity_type=request.entity_type,
                    record_id=request.record_id,
                    reason="unsupported_entity_type",
                    evidence={},
                )
            record = client.get_record(object_name=object_name, record_id=request.record_id)
            if record is not None:
                record = self._verification_view(request.entity_type, record)
        if record is None:
            return CrmVerificationResult(
                verified=False,
                provider_key="salesforce",
                entity_type=request.entity_type,
                record_id=request.record_id,
                reason="record_not_found",
                evidence={},
            )
        mismatches = {
            key: {"expected": value, "actual": record.get(key)}
            for key, value in request.expected_fields.items()
            if value is not None and record.get(key) != value
        }
        verified = not mismatches
        return CrmVerificationResult(
            verified=verified,
            provider_key="salesforce",
            entity_type=request.entity_type,
            record_id=request.record_id,
            reason="provider_readback_match" if verified else "field_mismatch",
            evidence={"record": record, "mismatches": mismatches},
        )

    def build_snapshot(self, connection: CrmConnectionRef) -> dict[str, object]:
        if not self._live_requested(connection):
            return self._store.build_snapshot(connection)
        try:
            self._live_client(connection)
        except (RuntimeError, ValueError) as exc:
            return {
                "provider_key": "salesforce",
                "live_api": True,
                "snapshot_available": False,
                "reason": str(exc),
            }
        return {
            "provider_key": "salesforce",
            "live_api": True,
            "snapshot_available": False,
            "reason": "live_contact_deal_listing_not_implemented",
        }
