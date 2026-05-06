from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from core.tenancy.normalization import require_tenant_id


CANON_TENANT_QUEUE_SCOPE = True
_ALLOWED_KINDS = {'job', 'dedupe', 'owner', 'worker', 'partition', 'tag'}


@dataclass(frozen=True)
class TenantQueueScope:
    tenant_id: str
    queue_name: str
    namespace: str = 'runtime'

    def validate(self) -> None:
        require_tenant_id(self.tenant_id)
        self._clean_segment(self.queue_name, field_name='queue_name')
        self._clean_segment(self.namespace, field_name='namespace')

    @property
    def scope_key(self) -> str:
        self.validate()
        return (
            f"tenant/{require_tenant_id(self.tenant_id)}"
            f"/{self._clean_segment(self.namespace, field_name='namespace')}"
            f"/queue/{self._clean_segment(self.queue_name, field_name='queue_name')}"
        )

    def qualify_job_id(self, job_id: str) -> str:
        return f"{self.scope_key}/job/{self._clean_segment(job_id, field_name='job_id')}"

    def qualify_dedupe_key(self, dedupe_key: str) -> str:
        return f"{self.scope_key}/dedupe/{self._clean_segment(dedupe_key, field_name='dedupe_key')}"

    def qualify_owner_id(self, owner_id: str) -> str:
        return f"{self.scope_key}/owner/{self._clean_segment(owner_id, field_name='owner_id')}"

    def qualify_worker_id(self, worker_id: str) -> str:
        return f"{self.scope_key}/worker/{self._clean_segment(worker_id, field_name='worker_id')}"

    def qualify_partition(self, partition: str) -> str:
        return f"{self.scope_key}/partition/{self._clean_segment(partition, field_name='partition')}"

    def qualify_tag(self, tag: str) -> str:
        return f"{self.scope_key}/tag/{self._clean_segment(tag, field_name='tag')}"

    def qualify_tags(self, tags: tuple[str, ...] | list[str] | None) -> tuple[str, ...]:
        return tuple(self.qualify_tag(tag) for tag in tuple(tags or ()))

    def belongs_to_scope(self, qualified_key: str) -> bool:
        text = str(qualified_key or '').strip()
        return bool(text) and (text == self.scope_key or text.startswith(self.scope_key + '/'))

    def assert_belongs_to_scope(self, qualified_key: str) -> None:
        if not self.belongs_to_scope(qualified_key):
            raise ValueError(
                f'qualified key does not belong to scope tenant={self.tenant_id} queue={self.queue_name}'
            )

    def assert_job_mapping(self, payload: Mapping[str, object]) -> None:
        if not isinstance(payload, Mapping):
            raise TypeError('payload must be a mapping')
        incoming_tenant_id = require_tenant_id(payload.get('tenant_id'))
        incoming_queue_name = self._clean_segment(payload.get('queue_name'), field_name='queue_name')
        if incoming_tenant_id != require_tenant_id(self.tenant_id):
            raise ValueError(
                f'cross-tenant queue payload is forbidden: expected tenant={self.tenant_id} got tenant={incoming_tenant_id}'
            )
        if incoming_queue_name != self._clean_segment(self.queue_name, field_name='queue_name'):
            raise ValueError(
                f'queue mismatch for tenant={self.tenant_id}: expected queue={self.queue_name} got queue={incoming_queue_name}'
            )
        job_id = payload.get('job_id')
        qualified_job_id = payload.get('qualified_job_id')
        if job_id is not None and qualified_job_id is not None:
            expected = self.qualify_job_id(str(job_id))
            actual = str(qualified_job_id).strip()
            if actual != expected:
                raise ValueError(
                    f'qualified_job_id mismatch for tenant={self.tenant_id}: expected {expected!r} got {actual!r}'
                )

    def parse_qualified_key(self, qualified_key: str) -> dict[str, str]:
        text = str(qualified_key or '').strip()
        if not text:
            raise ValueError('qualified_key is required')
        parts = text.split('/')
        if len(parts) != 7:
            raise ValueError('qualified_key is malformed')
        if parts[0] != 'tenant' or parts[3] != 'queue':
            raise ValueError('qualified_key must follow tenant/<tenant>/<namespace>/queue/<queue>/<kind>/<value> format')
        tenant_id = require_tenant_id(parts[1])
        namespace = self._clean_segment(parts[2], field_name='namespace')
        queue_name = self._clean_segment(parts[4], field_name='queue_name')
        kind = self._clean_kind(parts[5])
        value = self._clean_segment(parts[6], field_name='value')
        parsed = {
            'tenant_id': tenant_id,
            'namespace': namespace,
            'queue_name': queue_name,
            'kind': kind,
            'value': value,
        }
        if tenant_id != require_tenant_id(self.tenant_id):
            raise ValueError(
                f'cross-tenant qualified key is forbidden: expected tenant={self.tenant_id} got tenant={tenant_id}'
            )
        if queue_name != self._clean_segment(self.queue_name, field_name='queue_name'):
            raise ValueError(
                f'qualified key queue mismatch: expected queue={self.queue_name} got queue={queue_name}'
            )
        if namespace != self._clean_segment(self.namespace, field_name='namespace'):
            raise ValueError(
                f'qualified key namespace mismatch: expected namespace={self.namespace} got namespace={namespace}'
            )
        return parsed

    @classmethod
    def from_job_mapping(cls, payload: Mapping[str, object], *, namespace: str = 'runtime') -> 'TenantQueueScope':
        if not isinstance(payload, Mapping):
            raise TypeError('payload must be a mapping')
        return cls(
            tenant_id=require_tenant_id(payload.get('tenant_id')),
            queue_name=cls._clean_segment(payload.get('queue_name'), field_name='queue_name'),
            namespace=cls._clean_segment(namespace, field_name='namespace'),
        )

    @classmethod
    def from_qualified_key(cls, qualified_key: str) -> 'TenantQueueScope':
        text = str(qualified_key or '').strip()
        if not text:
            raise ValueError('qualified_key is required')
        parts = text.split('/')
        if len(parts) != 7 or parts[0] != 'tenant' or parts[3] != 'queue':
            raise ValueError('qualified_key must follow tenant/<tenant>/<namespace>/queue/<queue>/<kind>/<value> format')
        cls._clean_kind(parts[5])
        return cls(
            tenant_id=require_tenant_id(parts[1]),
            namespace=cls._clean_segment(parts[2], field_name='namespace'),
            queue_name=cls._clean_segment(parts[4], field_name='queue_name'),
        )

    @staticmethod
    def _clean_kind(value: object) -> str:
        kind = TenantQueueScope._clean_segment(value, field_name='kind')
        if kind not in _ALLOWED_KINDS:
            raise ValueError(f'kind is not supported: {kind}')
        return kind

    @staticmethod
    def _clean_segment(value: object, *, field_name: str) -> str:
        text = str(value or '').strip()
        if not text:
            raise ValueError(f'{field_name} is required')
        for forbidden in ('/', '\\', ':', '\n', '\r', '\t'):
            if forbidden in text:
                raise ValueError(f'{field_name} contains forbidden character: {forbidden!r}')
        if text in {'.', '..'}:
            raise ValueError(f'{field_name} contains forbidden reserved segment')
        return text


__all__ = ['CANON_TENANT_QUEUE_SCOPE', 'TenantQueueScope']
