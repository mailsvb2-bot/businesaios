from __future__ import annotations

from collections.abc import Mapping
from typing import Any
from urllib.parse import quote

from crm.providers.common.crm_http_client import CrmHttpClient, CrmHttpRequest, CrmHttpResponse
from crm.providers.common.crm_http_errors import CrmResponseError
from crm.providers.salesforce.salesforce_api_config import SalesforceApiConfig


class SalesforceApiError(RuntimeError):
    pass


class SalesforceClient:
    """Salesforce REST client using BusinessAIOS's canonical CRM HTTP boundary."""

    def __init__(
        self,
        *,
        access_token: str,
        instance_url: str,
        config: SalesforceApiConfig | None = None,
        http_client: CrmHttpClient | None = None,
    ) -> None:
        if not access_token.strip():
            raise ValueError("Salesforce access token is required")
        self._config = config or SalesforceApiConfig()
        self._base = self._config.rest_base(instance_url)
        self._http = http_client or CrmHttpClient(
            base_url=self._base,
            default_headers={
                "Authorization": f"Bearer {access_token}",
                "Accept": "application/json",
            },
        )

    def _request(
        self,
        method: str,
        path: str,
        *,
        json: Mapping[str, object] | None = None,
        params: Mapping[str, object] | None = None,
        allow_not_found: bool = False,
    ) -> CrmHttpResponse | None:
        try:
            return self._http.send(
                CrmHttpRequest(
                    method=method,
                    path=path,
                    query_params=dict(params or {}),
                    json_body=dict(json) if json is not None else None,
                    timeout_seconds=self._config.timeout_seconds,
                )
            )
        except CrmResponseError as exc:
            if allow_not_found and exc.context.status_code == 404:
                return None
            raise

    @staticmethod
    def _dict_payload(response: CrmHttpResponse, *, context: str) -> dict[str, object]:
        if response.json_body is None:
            return {}
        if not isinstance(response.json_body, dict):
            raise SalesforceApiError(f"Salesforce {context} returned an unexpected JSON payload")
        return dict(response.json_body)

    def query(self, soql: str) -> list[dict[str, object]]:
        if not soql.strip():
            raise ValueError("SOQL query must not be blank")
        response = self._request("GET", "/query", params={"q": soql})
        if response is None:
            raise SalesforceApiError("Salesforce query unexpectedly returned not found")
        data = self._dict_payload(response, context="query")
        records = [dict(item) for item in (data.get("records") or []) if isinstance(item, dict)]
        next_url = data.get("nextRecordsUrl")
        while next_url:
            marker = f"/services/data/{self._config.api_version}/"
            next_url_text = str(next_url)
            if not next_url_text.startswith(marker):
                raise SalesforceApiError("Salesforce returned an invalid nextRecordsUrl")
            page = self._request("GET", "/" + next_url_text[len(marker):])
            if page is None:
                raise SalesforceApiError("Salesforce query page unexpectedly returned not found")
            data = self._dict_payload(page, context="query page")
            records.extend(dict(item) for item in (data.get("records") or []) if isinstance(item, dict))
            next_url = data.get("nextRecordsUrl")
        return records

    def get_record(self, *, object_name: str, record_id: str) -> dict[str, object] | None:
        if not record_id:
            return None
        path = f'/sobjects/{quote(object_name, safe="")}/{quote(record_id, safe="")}'
        response = self._request("GET", path, allow_not_found=True)
        if response is None:
            return None
        return self._dict_payload(response, context="record read")

    def get_external(
        self,
        *,
        object_name: str,
        external_id_field: str,
        external_id: str,
    ) -> dict[str, object] | None:
        if not external_id:
            return None
        path = (
            f'/sobjects/{quote(object_name, safe="")}/'
            f'{quote(external_id_field, safe="")}/{quote(external_id, safe="")}'
        )
        response = self._request("GET", path, allow_not_found=True)
        if response is None:
            return None
        return self._dict_payload(response, context="external-id read")

    def upsert_external(
        self,
        *,
        object_name: str,
        external_id_field: str,
        external_id: str,
        fields: Mapping[str, object],
    ) -> dict[str, object]:
        if not external_id:
            raise ValueError("Salesforce external ID must not be blank")
        path = (
            f'/sobjects/{quote(object_name, safe="")}/'
            f'{quote(external_id_field, safe="")}/{quote(external_id, safe="")}'
        )
        response = self._request("PATCH", path, json=fields)
        if response is None:
            raise SalesforceApiError("Salesforce upsert unexpectedly returned not found")
        payload = self._dict_payload(response, context="upsert")
        # Salesforce external-ID upsert distinguishes insert/update by HTTP
        # status even when an update has an empty 204 response body.
        payload["created"] = response.status_code == 201
        return payload
