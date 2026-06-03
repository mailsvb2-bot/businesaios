from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from collections.abc import Mapping

from application.business_autonomy.provider_admin_contract import ProviderDefinition
from application.business_autonomy.provider_runtime_contract import ProviderPaginationRunResult
from runtime.business_autonomy.provider_live_sync_runtime import ProviderLiveSyncRuntime

CANON_PROVIDER_PAGINATION_WALKERS = True


@dataclass(frozen=True)
class ProviderPaginationWalkers:
    runtime: ProviderLiveSyncRuntime

    def walk(self, *, provider: ProviderDefinition, tenant_id: str, business_id: str, operation: str, mode: str = 'dry_run', payload: Mapping[str, Any] | None = None, max_pages: int = 3) -> ProviderPaginationRunResult:
        normalized_payload = dict(payload or {})
        pages: list[dict[str, Any]] = []
        seen: set[str] = set()
        cursor = normalized_payload.get('cursor')
        status = 'pagination_no_pages'
        accepted = False
        for page_index in range(max(1, int(max_pages))):
            page_payload = dict(normalized_payload)
            if cursor not in {None, ''}:
                page_payload['cursor'] = cursor
            result = self.runtime.run(provider=provider, tenant_id=str(tenant_id), business_id=str(business_id), operation=operation, mode=mode, payload=page_payload)
            parsed = dict(result.metadata.get('parsed_response') or {})
            page_row = {'page_index': page_index, 'cursor_in': cursor, 'status': result.status, 'accepted': result.accepted, 'parsed_response': parsed, 'history_row': dict(result.metadata.get('history_row') or {})}
            pages.append(page_row)
            status = result.status
            accepted = accepted or bool(result.accepted)
            next_cursor = parsed.get('next_cursor')
            if next_cursor in {None, ''} or str(next_cursor) in seen:
                break
            seen.add(str(next_cursor))
            cursor = str(next_cursor)
        final_status = 'pagination_walk_complete' if pages else status
        return ProviderPaginationRunResult(provider_key=provider.provider_key, operation=operation, mode=str(mode or 'dry_run'), status=final_status, accepted=accepted, metadata={'pages': tuple(pages), 'page_count': len(pages), 'last_cursor': cursor, 'max_pages': max(1, int(max_pages))})


__all__ = ['CANON_PROVIDER_PAGINATION_WALKERS', 'ProviderPaginationWalkers']
