from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable
from collections.abc import Mapping

from contracts.platforms.market_intelligence_advanced_contract import ProviderCursor
from runtime._internal.market_intelligence.cursor_store import FileProviderCursorStore
from runtime._internal.market_intelligence.http_transport import CanonicalHttpTransport, HttpRequest
from runtime._internal.market_intelligence.pagination import PageCursor, PageResult, PaginationWindow, normalize_items
from runtime._internal.market_intelligence.provider_runtime import ProviderRuntimeError, ProviderRuntimeFactory
from runtime._internal.market_intelligence.recovery import MarketIntelligenceRecoveryController
from runtime._internal.market_intelligence.state_store import SqliteMarketIntelligenceStateStore, SyncCheckpoint

CANON_MARKET_INTELLIGENCE_PROVIDER_CLIENT = True
_MAX_TOTAL_LIMIT = 5000
_MAX_PAGE_LIMIT = 500


def _text(value: object, *, default: str = '') -> str:
    text = str(value or '').strip()
    return text or default


@dataclass(frozen=True)
class ProviderRequestPlan:
    provider: str
    source_family: str
    operation: str
    url: str
    method: str = 'GET'
    params: Mapping[str, Any] = field(default_factory=dict)
    headers: Mapping[str, str] = field(default_factory=dict)
    body: Mapping[str, Any] | None = None
    cursor_param: str = 'cursor'
    item_path: str = 'items'
    next_cursor_path: str = 'next_cursor'
    page_size_param: str = 'limit'
    page_size: int = 100
    max_pages: int = 10


class ProviderPlanRegistry:
    def __init__(self) -> None:
        self._builders: dict[tuple[str, str, str], Callable[[Mapping[str, Any]], ProviderRequestPlan]] = {}

    def register(self, *, provider: str, source_family: str, operation: str, builder: Callable[[Mapping[str, Any]], ProviderRequestPlan]) -> None:
        self._builders[(str(provider), str(source_family), str(operation))] = builder

    def resolve(self, *, provider: str, source_family: str, operation: str, payload: Mapping[str, Any]) -> ProviderRequestPlan:
        builder = self._builders.get((str(provider), str(source_family), str(operation)))
        if builder is None:
            raise KeyError(f'unknown provider plan: {provider}/{source_family}/{operation}')
        return builder(dict(payload or {}))

    def has(self, *, provider: str, source_family: str, operation: str) -> bool:
        return (str(provider), str(source_family), str(operation)) in self._builders


@dataclass
class MarketIntelligenceProviderClient:
    transport: CanonicalHttpTransport = field(default_factory=CanonicalHttpTransport)
    cursor_store: FileProviderCursorStore = field(default_factory=FileProviderCursorStore)
    plan_registry: ProviderPlanRegistry = field(default_factory=ProviderPlanRegistry)
    runtime_factory: ProviderRuntimeFactory = field(default_factory=ProviderRuntimeFactory)
    state_store: SqliteMarketIntelligenceStateStore = field(default_factory=SqliteMarketIntelligenceStateStore)
    recovery: MarketIntelligenceRecoveryController = field(default_factory=MarketIntelligenceRecoveryController)

    def __post_init__(self) -> None:
        if self.recovery.state_store is not self.state_store:
            self.recovery.state_store = self.state_store

    def execute_market_intelligence(self, *, provider: str, source_family: str, operation: str, payload: Mapping[str, Any], dry_run: bool) -> Mapping[str, Any]:
        if self.plan_registry.has(provider=provider, source_family=source_family, operation=operation):
            return self._execute_legacy_plan(provider=provider, source_family=source_family, operation=operation, payload=payload, dry_run=dry_run)
        return self._execute_enterprise_plan(provider=provider, source_family=source_family, operation=operation, payload=payload, dry_run=dry_run)

    def _execute_legacy_plan(self, *, provider: str, source_family: str, operation: str, payload: Mapping[str, Any], dry_run: bool) -> Mapping[str, Any]:
        plan = self.plan_registry.resolve(provider=provider, source_family=source_family, operation=operation, payload=payload)
        tenant_id = _text(payload.get('tenant_id'), default='default')
        scope_key = self._scope_key(payload)
        current = self.cursor_store.load(tenant_id=tenant_id, provider=provider, source_family=source_family, scope_key=scope_key)
        requested_total_limit = self._bounded_int(payload.get('limit'), default=plan.page_size * plan.max_pages, upper=_MAX_TOTAL_LIMIT)
        requested_page_limit = self._bounded_int(payload.get('page_limit') or payload.get('page_size'), default=plan.page_size, upper=_MAX_PAGE_LIMIT)
        if dry_run:
            return {
                'ok': True,
                'code': 'dry_run',
                'provider': provider,
                'source_family': source_family,
                'operation': operation,
                'cursor': current.as_dict(),
                'records': [],
                'plan': {
                    'url': plan.url,
                    'method': plan.method,
                    'params': dict(plan.params),
                    'page_limit': requested_page_limit,
                    'total_limit': requested_total_limit,
                    'max_pages': plan.max_pages,
                },
            }
        window = PaginationWindow(max_pages=plan.max_pages, max_items=requested_total_limit)
        summary = window.collect_summary(lambda cursor: self._fetch_page(plan=plan, payload=payload, cursor=cursor, requested_page_limit=requested_page_limit))
        rows = summary.rows
        new_cursor = ProviderCursor(
            tenant_id=tenant_id,
            provider=provider,
            source_family=source_family,
            scope_key=scope_key,
            cursor=summary.final_cursor_token or self._last_record_token(rows) or current.cursor,
            last_seen_at=self._last_seen_at(rows) or current.last_seen_at,
            checksum=self._checksum(rows) if rows else (current.checksum or self._checksum(())),
            metadata={
                'operation': operation,
                'records': len(rows),
                'pages_fetched': summary.pages_fetched,
                'exhausted': summary.exhausted,
                'requested_page_limit': requested_page_limit,
                'requested_total_limit': requested_total_limit,
                'page_metadata': [dict(item) for item in summary.page_metadata[-5:]],
            },
        )
        self.cursor_store.save(new_cursor)
        return {
            'ok': True,
            'code': 'executed',
            'provider': provider,
            'source_family': source_family,
            'operation': operation,
            'cursor': new_cursor.as_dict(),
            'records': list(rows),
        }

    def _execute_enterprise_plan(self, *, provider: str, source_family: str, operation: str, payload: Mapping[str, Any], dry_run: bool) -> Mapping[str, Any]:
        tenant_id = _text(payload.get('tenant_id'), default='default')
        scope_key = self._scope_key(payload)
        request_fingerprint = self._request_fingerprint(payload)
        preflight = self.recovery.preflight(
            tenant_id=tenant_id,
            provider=provider,
            source_family=source_family,
            scope_key=scope_key,
            operation=operation,
            request_fingerprint=request_fingerprint,
        )
        if not preflight.allowed:
            raise ProviderRuntimeError('quarantined_source', f'provider scope is quarantined: {preflight.reason}', provider=provider, details={'scope_key': scope_key})
        if preflight.replay_hit and not dry_run:
            checkpoint = self.state_store.load_checkpoint(tenant_id=tenant_id, provider=provider, source_family=source_family, scope_key=scope_key)
            return {
                'ok': True,
                'executed': True,
                'code': 'replay_hit',
                'provider': provider,
                'source_family': source_family,
                'operation': operation,
                'records': [],
                'cursor': checkpoint.cursor,
                'tenant_id': tenant_id,
                'replay_key': preflight.replay_key,
                'resume_cursor': preflight.resume_cursor,
            }
        run_id = f'mi:{hashlib.sha1(f"{tenant_id}|{provider}|{scope_key}|{request_fingerprint}".encode()).hexdigest()[:24]}'
        checkpoint_before = self.state_store.load_checkpoint(tenant_id=tenant_id, provider=provider, source_family=source_family, scope_key=scope_key)
        self.state_store.begin_run(
            run_id=run_id,
            tenant_id=tenant_id,
            provider=provider,
            source_family=source_family,
            scope_key=scope_key,
            operation=operation,
            replay_key=preflight.replay_key,
            checkpoint_before=checkpoint_before,
            metadata={'request_fingerprint': request_fingerprint},
        )
        plan = self.runtime_factory.build_plan(provider=provider, operation=operation, payload=payload)
        requested_total_limit = self._bounded_int(payload.get('limit'), default=100, upper=_MAX_TOTAL_LIMIT)
        requested_page_limit = self._bounded_int(payload.get('page_limit') or payload.get('page_size'), default=50, upper=_MAX_PAGE_LIMIT)
        if dry_run:
            return {
                'ok': True,
                'executed': True,
                'code': 'dry_run',
                'provider': plan.provider,
                'source_family': plan.source_family,
                'operation': operation,
                'records': [],
                'cursor': checkpoint_before.cursor,
                'run_id': run_id,
                'tenant_id': tenant_id,
                'manifest': dict(plan.manifest),
                'replay_key': preflight.replay_key,
                'resume_cursor': preflight.resume_cursor,
            }
        try:
            summary = PaginationWindow(max_pages=plan.max_pages, max_items=requested_total_limit).collect_summary(
                lambda cursor: self._fetch_page_runtime(plan=plan, payload=payload, cursor=cursor, page_limit=requested_page_limit)
            )
            normalized_rows = self.runtime_factory.normalize_records(provider=plan.provider, operation=operation, source_family=plan.source_family, records=[dict(row) for row in summary.rows])
            checkpoint_after = SyncCheckpoint(
                tenant_id=tenant_id,
                provider=plan.provider,
                source_family=plan.source_family,
                scope_key=scope_key,
                cursor=summary.final_cursor_token or self._last_record_token(tuple(normalized_rows)) or checkpoint_before.cursor,
                last_seen_at=self._last_seen_at(tuple(normalized_rows)) or checkpoint_before.last_seen_at,
                checksum=self._checksum(tuple(normalized_rows)),
                metadata={
                    'operation': operation,
                    'pages_fetched': summary.pages_fetched,
                    'records_count': len(normalized_rows),
                    'request_fingerprint': request_fingerprint,
                    'manifest_version': plan.version,
                },
            )
            self.state_store.save_checkpoint(checkpoint_after)
            self.state_store.finish_run(run_id=run_id, status='succeeded', checkpoint_after=checkpoint_after, records_count=len(normalized_rows), pages_fetched=summary.pages_fetched)
            return {
                'ok': True,
                'executed': True,
                'code': 'executed',
                'provider': plan.provider,
                'source_family': plan.source_family,
                'operation': operation,
                'records': normalized_rows,
                'cursor': checkpoint_after.cursor,
                'run_id': run_id,
                'tenant_id': tenant_id,
                'manifest': dict(plan.manifest),
                'replay_key': preflight.replay_key,
                'resume_cursor': preflight.resume_cursor,
                'page_metadata': [dict(item) for item in summary.page_metadata],
            }
        except Exception as exc:
            mapped = self.runtime_factory.map_transport_error(provider=provider, exc=exc) if not isinstance(exc, ProviderRuntimeError) else exc
            poisoned = mapped.code in {'contract_violation', 'invalid_response'}
            quarantined = poisoned
            if quarantined:
                self.recovery.quarantine_poisoned_source(tenant_id=tenant_id, provider=provider, source_family=source_family, scope_key=scope_key, reason_code=mapped.code, details=mapped.details)
            checkpoint_after = self.state_store.load_checkpoint(tenant_id=tenant_id, provider=provider, source_family=source_family, scope_key=scope_key)
            self.state_store.finish_run(
                run_id=run_id,
                status='failed',
                checkpoint_after=checkpoint_after,
                records_count=0,
                pages_fetched=0,
                error_code=mapped.code,
                error_message=str(mapped),
                poisoned=poisoned,
                quarantined=quarantined,
            )
            raise

    def _fetch_page(self, *, plan: ProviderRequestPlan, payload: Mapping[str, Any], cursor: PageCursor | None, requested_page_limit: int) -> PageResult:
        params = dict(plan.params)
        params.setdefault(plan.page_size_param, requested_page_limit)
        if cursor and cursor.token:
            params[plan.cursor_param] = cursor.token
        response = self.transport.execute(
            plan.provider,
            HttpRequest(
                method=plan.method,
                url=plan.url,
                params=params,
                headers=plan.headers,
                body=plan.body,
                timeout_seconds=float(payload.get('timeout_seconds') or 20.0),
            ),
        )
        items = self._extract_items(response.json_payload, plan.item_path)
        next_token = self._extract_scalar(response.json_payload, plan.next_cursor_path)
        return PageResult(items=normalize_items(items), next_cursor=PageCursor(token=next_token, page_number=(cursor.page_number + 1 if cursor else 2)) if next_token else None, exhausted=not bool(next_token), metadata={'status_code': response.status_code, 'next_cursor_token': next_token})

    def _fetch_page_runtime(self, *, plan: Any, payload: Mapping[str, Any], cursor: PageCursor | None, page_limit: int) -> PageResult:
        req = plan.request
        params = dict(req.params)
        params.setdefault(plan.page_size_param, page_limit)
        if cursor and cursor.token:
            params[plan.cursor_param] = cursor.token
        response = self.transport.execute(
            plan.provider,
            req.__class__(
                method=req.method,
                url=req.url,
                params=params,
                headers=req.headers,
                body=req.body,
                timeout_seconds=req.timeout_seconds,
                accept_json=req.accept_json,
            ),
        )
        json_payload = response.json_payload
        items = self._extract_items(json_payload, plan.item_path)
        next_token = self._extract_scalar(json_payload, plan.next_cursor_path)
        return PageResult(items=normalize_items(items), next_cursor=PageCursor(token=next_token, page_number=(cursor.page_number + 1 if cursor else 2)) if next_token else None, exhausted=not bool(next_token), metadata={'status_code': response.status_code, 'next_cursor_token': next_token})

    def _extract_items(self, payload: object, path: str) -> object:
        if path in {'', '.', '$'}:
            return payload
        current: object = payload
        for token in str(path).split('.'):
            if token in {'', '$'}:
                continue
            if not isinstance(current, Mapping):
                return []
            current = current.get(token)
        return current

    def _extract_scalar(self, payload: object, path: str) -> str | None:
        if path in {'', '.', '$'}:
            text = _text(payload)
            return text or None
        current: object = payload
        for token in str(path).split('.'):
            if token in {'', '$'}:
                continue
            if not isinstance(current, Mapping):
                return None
            current = current.get(token)
        text = _text(current)
        return text or None

    def _scope_key(self, payload: Mapping[str, Any]) -> str:
        pieces = [_text(payload.get('query')), _text(payload.get('subject_url')), _text(payload.get('account_ref')), _text(payload.get('region')), _text(payload.get('locale'))]
        joined = '|'.join(piece for piece in pieces if piece)
        if len(joined) > 180:
            return hashlib.sha256(joined.encode('utf-8', errors='replace')).hexdigest()
        return joined or 'global'

    def _request_fingerprint(self, payload: Mapping[str, Any]) -> str:
        safe = {str(k): payload[k] for k in sorted(payload.keys()) if str(k) not in {'idempotency_key', 'risk'}}
        return hashlib.sha256(repr(sorted(safe.items())).encode('utf-8')).hexdigest()

    def _last_record_token(self, rows: tuple[dict[str, Any], ...]) -> str | None:
        if not rows:
            return None
        last = rows[-1]
        return _text(last.get('cursor') or last.get('record_id') or last.get('external_id') or last.get('id')) or None

    def _last_seen_at(self, rows: tuple[dict[str, Any], ...]) -> str | None:
        if not rows:
            return None
        last = rows[-1]
        return _text(last.get('updated_at') or last.get('published_at') or last.get('observed_at')) or None

    def _checksum(self, rows: tuple[dict[str, Any], ...] | tuple[()]) -> str:
        digest = hashlib.sha256()
        for row in rows:
            digest.update(repr(sorted(dict(row).items())).encode('utf-8', errors='replace'))
        return digest.hexdigest()

    def _bounded_int(self, value: object, *, default: int, upper: int) -> int:
        try:
            number = int(value)
        except (TypeError, ValueError):
            number = int(default)
        return max(1, min(number, int(upper)))


__all__ = [
    'CANON_MARKET_INTELLIGENCE_PROVIDER_CLIENT',
    'MarketIntelligenceProviderClient',
    'ProviderPlanRegistry',
    'ProviderRequestPlan',
]
