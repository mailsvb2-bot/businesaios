from __future__ import annotations

from pathlib import Path


def replace_once(path: str, old: str, new: str) -> None:
    target = Path(path)
    text = target.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"expected one marker in {path}, found {count}: {old[:100]!r}")
    target.write_text(text.replace(old, new, 1), encoding="utf-8")


replace_once(
    "application/business_autonomy/guards.py",
    "from application.business_autonomy.contracts import BusinessExecutionRequest\n",
    "from application.business_autonomy.contracts import BusinessExecutionRequest\n"
    "from application.business_autonomy.execution_subject import parse_business_idempotency_token\n",
)

replace_once(
    "application/business_autonomy/guards.py",
    '''class BusinessIdempotencyReservationStatus(str, Enum):
    ACCEPTED = "accepted"
    REPLAY_COMPLETED = "replay_completed"
    IN_PROGRESS = "in_progress"
    TERMINAL_FAILED = "terminal_failed"


@dataclass(frozen=True)
class BusinessIdempotencyReservation:
    status: BusinessIdempotencyReservationStatus
    payload: object | None = None


@dataclass
class _BusinessIdempotencyRecord:
    owner_id: str
    state: str
    payload: object | None = None
    failure_reason: str | None = None


class BusinessIdempotencyStore:
    """Process-local compatibility store with reserve-before-effect semantics."""

    def __init__(self) -> None:
        self._items: dict[str, _BusinessIdempotencyRecord] = {}
        self._lock = RLock()

    def get(self, key: str):
        with self._lock:
            record = self._items.get(str(key))
            if record is None or record.state != "completed":
                return None
            return record.payload

    def reserve(self, key: str, *, owner_id: str) -> BusinessIdempotencyReservation:
        normalized_key = str(key).strip()
        normalized_owner = str(owner_id).strip()
        if not normalized_key:
            raise ValueError("idempotency key is required")
        if not normalized_owner:
            raise ValueError("idempotency owner is required")
        with self._lock:
            current = self._items.get(normalized_key)
            if current is None:
                self._items[normalized_key] = _BusinessIdempotencyRecord(owner_id=normalized_owner, state="in_progress")
                return BusinessIdempotencyReservation(BusinessIdempotencyReservationStatus.ACCEPTED)
            if current.state == "completed":
                return BusinessIdempotencyReservation(BusinessIdempotencyReservationStatus.REPLAY_COMPLETED, current.payload)
            if current.state == "failed":
                return BusinessIdempotencyReservation(BusinessIdempotencyReservationStatus.TERMINAL_FAILED)
            return BusinessIdempotencyReservation(BusinessIdempotencyReservationStatus.IN_PROGRESS)

    def complete(self, key: str, *, owner_id: str, payload: object) -> None:
        with self._lock:
            current = self._items.get(str(key))
            if current is None or current.owner_id != str(owner_id) or current.state != "in_progress":
                raise ValueError("idempotency reservation ownership mismatch")
            current.state = "completed"
            current.payload = payload
            current.failure_reason = None

    def fail(self, key: str, *, owner_id: str, reason: str) -> None:
        with self._lock:
            current = self._items.get(str(key))
            if current is None or current.owner_id != str(owner_id) or current.state != "in_progress":
                raise ValueError("idempotency reservation ownership mismatch")
            current.state = "failed"
            current.failure_reason = str(reason)

    def put(self, key: str, payload: object) -> None:
        """Compatibility terminal cache for a rejection that occurred before effects."""
        normalized_key = str(key).strip()
        if not normalized_key:
            raise ValueError("idempotency key is required")
        with self._lock:
            current = self._items.get(normalized_key)
            if current is None:
                self._items[normalized_key] = _BusinessIdempotencyRecord(
                    owner_id="compatibility-cache",
                    state="completed",
                    payload=payload,
                )
''',
    '''class BusinessIdempotencyReservationStatus(str, Enum):
    ACCEPTED = "accepted"
    REPLAY_COMPLETED = "replay_completed"
    IN_PROGRESS = "in_progress"
    TERMINAL_FAILED = "terminal_failed"
    SCOPE_MISMATCH = "scope_mismatch"


@dataclass(frozen=True)
class BusinessIdempotencyReservation:
    status: BusinessIdempotencyReservationStatus
    payload: object | None = None


@dataclass
class _BusinessIdempotencyRecord:
    owner_id: str
    state: str
    scope_fingerprint: str
    payload: object | None = None
    failure_reason: str | None = None


class BusinessIdempotencyStore:
    """Process-local compatibility store with subject-bound reserve-before-effect semantics."""

    def __init__(self) -> None:
        self._items: dict[str, _BusinessIdempotencyRecord] = {}
        self._lock = RLock()

    @staticmethod
    def _parts(key: str) -> tuple[str, str]:
        return parse_business_idempotency_token(key)

    def get(self, key: str):
        stable_key, scope_fingerprint = self._parts(key)
        with self._lock:
            record = self._items.get(stable_key)
            if (
                record is None
                or record.scope_fingerprint != scope_fingerprint
                or record.state != "completed"
            ):
                return None
            return record.payload

    def reserve(self, key: str, *, owner_id: str) -> BusinessIdempotencyReservation:
        stable_key, scope_fingerprint = self._parts(key)
        normalized_owner = str(owner_id).strip()
        if not normalized_owner:
            raise ValueError("idempotency owner is required")
        with self._lock:
            current = self._items.get(stable_key)
            if current is None:
                self._items[stable_key] = _BusinessIdempotencyRecord(
                    owner_id=normalized_owner,
                    state="in_progress",
                    scope_fingerprint=scope_fingerprint,
                )
                return BusinessIdempotencyReservation(BusinessIdempotencyReservationStatus.ACCEPTED)
            if current.scope_fingerprint != scope_fingerprint:
                return BusinessIdempotencyReservation(BusinessIdempotencyReservationStatus.SCOPE_MISMATCH)
            if current.state == "completed":
                return BusinessIdempotencyReservation(BusinessIdempotencyReservationStatus.REPLAY_COMPLETED, current.payload)
            if current.state == "failed":
                return BusinessIdempotencyReservation(BusinessIdempotencyReservationStatus.TERMINAL_FAILED)
            return BusinessIdempotencyReservation(BusinessIdempotencyReservationStatus.IN_PROGRESS)

    def complete(self, key: str, *, owner_id: str, payload: object) -> None:
        stable_key, scope_fingerprint = self._parts(key)
        with self._lock:
            current = self._items.get(stable_key)
            if (
                current is None
                or current.owner_id != str(owner_id)
                or current.state != "in_progress"
                or current.scope_fingerprint != scope_fingerprint
            ):
                raise ValueError("idempotency reservation ownership or scope mismatch")
            current.state = "completed"
            current.payload = payload
            current.failure_reason = None

    def fail(self, key: str, *, owner_id: str, reason: str) -> None:
        stable_key, scope_fingerprint = self._parts(key)
        with self._lock:
            current = self._items.get(stable_key)
            if (
                current is None
                or current.owner_id != str(owner_id)
                or current.state != "in_progress"
                or current.scope_fingerprint != scope_fingerprint
            ):
                raise ValueError("idempotency reservation ownership or scope mismatch")
            current.state = "failed"
            current.failure_reason = str(reason)

    def put(self, key: str, payload: object) -> None:
        """Compatibility terminal cache for a rejection produced before effects."""
        stable_key, scope_fingerprint = self._parts(key)
        with self._lock:
            current = self._items.get(stable_key)
            if current is None:
                self._items[stable_key] = _BusinessIdempotencyRecord(
                    owner_id="compatibility-cache",
                    state="completed",
                    scope_fingerprint=scope_fingerprint,
                    payload=payload,
                )
''',
)

replace_once(
    "application/business_autonomy/persistence.py",
    "from application.business_autonomy.trust import BusinessTrustSnapshot, BusinessTrustTier\n",
    "from application.business_autonomy.execution_subject import (\n"
    "    approval_subject_metadata,\n"
    "    business_execution_approval_id,\n"
    "    business_execution_fingerprint,\n"
    "    parse_business_idempotency_token,\n"
    ")\n"
    "from application.business_autonomy.trust import BusinessTrustSnapshot, BusinessTrustTier\n",
)

replace_once(
    "application/business_autonomy/persistence.py",
    '''        metadata = dict(request.envelope.metadata)
        tenant_id = str(metadata.get("tenant_id") or "").strip()
        if not tenant_id or tenant_id == "global":
            return GateDecision(GateStatus.REJECTED, "Canonical approval requires an explicit tenant.")
        approval_id = str(metadata.get("approval_id") or f"business-autonomy:{request.envelope.business_id}:{request.envelope.goal_id}")
        existing = self._store.get(approval_id)
        if existing is None:
            approval_request = ApprovalRequest(
                approval_id=approval_id,
                tenant_id=tenant_id,
                subject_type="business_autonomy_execution",
                subject_id=str(request.envelope.goal_id),
                requested_by=str(request.envelope.requested_by or "platform"),
                reason=str(metadata.get("approval_reason") or "Business autonomy execution requires approval."),
                metadata={
                    "business_id": request.envelope.business_id,
                    "goal_id": request.envelope.goal_id,
                    "goal_type": request.envelope.goal_type,
                },
            )
            try:
                existing = self._store.create(approval_request)
            except ValueError:
                existing = self._store.get(approval_id)

        if existing is None:
            return GateDecision(GateStatus.PENDING, "Approval request could not be resolved.")
        bound_business_id = str(existing.request.metadata.get("business_id") or "")
        if (
            existing.request.tenant_id != tenant_id
            or existing.request.subject_type != "business_autonomy_execution"
            or existing.request.subject_id != str(request.envelope.goal_id)
            or bound_business_id != str(request.envelope.business_id)
        ):
            return GateDecision(GateStatus.REJECTED, "Approval binding mismatch.")
''',
    '''        metadata = dict(request.envelope.metadata)
        tenant_id = str(metadata.get("tenant_id") or "").strip()
        if not tenant_id or tenant_id == "global":
            return GateDecision(GateStatus.REJECTED, "Canonical approval requires an explicit tenant.")
        approval_id = business_execution_approval_id(request)
        subject_fingerprint = business_execution_fingerprint(request)
        existing = self._store.get(approval_id)
        if existing is None:
            approval_request = ApprovalRequest(
                approval_id=approval_id,
                tenant_id=tenant_id,
                subject_type="business_autonomy_execution",
                subject_id=str(request.envelope.goal_id),
                requested_by=str(request.envelope.requested_by or "platform"),
                reason=str(metadata.get("approval_reason") or "Business autonomy execution requires approval."),
                metadata=dict(approval_subject_metadata(request)),
            )
            try:
                existing = self._store.create(approval_request)
            except ValueError:
                existing = self._store.get(approval_id)

        if existing is None:
            return GateDecision(GateStatus.PENDING, "Approval request could not be resolved.")
        bound_business_id = str(existing.request.metadata.get("business_id") or "")
        bound_fingerprint = str(existing.request.metadata.get("subject_fingerprint") or "")
        if (
            existing.request.approval_id != approval_id
            or existing.request.tenant_id != tenant_id
            or existing.request.subject_type != "business_autonomy_execution"
            or existing.request.subject_id != str(request.envelope.goal_id)
            or bound_business_id != str(request.envelope.business_id)
            or bound_fingerprint != subject_fingerprint
        ):
            return GateDecision(GateStatus.REJECTED, "Approval binding mismatch.")
''',
)

replace_once(
    "application/business_autonomy/persistence.py",
    '''    @staticmethod
    def _idem_key(raw_key: str):
        return build_idempotency_key(
            tenant_id="global",
            namespace="business_autonomy",
            operation="execute",
            key=str(raw_key),
            semantic_scope={"business_autonomy_key": str(raw_key)},
        )
''',
    '''    @staticmethod
    def _idem_key(raw_key: str):
        stable_key, subject_fingerprint = parse_business_idempotency_token(raw_key)
        tenant_id = stable_key.split(":", 1)[0]
        return build_idempotency_key(
            tenant_id=tenant_id,
            namespace="business_autonomy",
            operation="execute",
            key=stable_key,
            semantic_scope={"execution_subject_fingerprint": subject_fingerprint},
        )
''',
)

replace_once(
    "application/business_autonomy/guarded_service.py",
    "from application.business_autonomy.contracts import BusinessExecutionRequest, BusinessExecutionResult, ExecutionVerdict\n",
    "from application.business_autonomy.contracts import BusinessExecutionRequest, BusinessExecutionResult, ExecutionVerdict\n"
    "from application.business_autonomy.execution_subject import scoped_business_idempotency_token\n",
)

replace_once(
    "application/business_autonomy/guarded_service.py",
    '''        if reservation.status == BusinessIdempotencyReservationStatus.IN_PROGRESS:
            return BusinessExecutionResult(
                verdict=ExecutionVerdict.PARTIAL,
                business_id=effective_request.envelope.business_id,
                goal_id=effective_request.envelope.goal_id,
                execution_id=effective_request.correlation_id,
                message="An execution with this idempotency key is already in progress.",
                metadata={"idempotency_status": reservation.status.value},
            )
        if reservation.status != BusinessIdempotencyReservationStatus.ACCEPTED:
''',
    '''        if reservation.status == BusinessIdempotencyReservationStatus.IN_PROGRESS:
            return BusinessExecutionResult(
                verdict=ExecutionVerdict.PARTIAL,
                business_id=effective_request.envelope.business_id,
                goal_id=effective_request.envelope.goal_id,
                execution_id=effective_request.correlation_id,
                message="An execution with this idempotency key is already in progress.",
                metadata={"idempotency_status": reservation.status.value},
            )
        if reservation.status == BusinessIdempotencyReservationStatus.SCOPE_MISMATCH:
            return BusinessExecutionResult(
                verdict=ExecutionVerdict.REJECTED,
                business_id=effective_request.envelope.business_id,
                goal_id=effective_request.envelope.goal_id,
                execution_id=effective_request.correlation_id,
                message="The idempotency key was reused with a different canonical execution subject.",
                metadata={"idempotency_status": reservation.status.value},
            )
        if reservation.status != BusinessIdempotencyReservationStatus.ACCEPTED:
''',
)

replace_once(
    "application/business_autonomy/guarded_service.py",
    '''def _scoped_idempotency_key(request: BusinessExecutionRequest) -> str:
    tenant_id = str(request.envelope.metadata.get("tenant_id") or "global").strip() or "global"
    business_id = str(request.envelope.business_id or "unknown").strip() or "unknown"
    raw_key = str(request.idempotency_key or request.correlation_id).strip() or str(request.correlation_id)
    return f"{tenant_id}:{business_id}:{raw_key}"
''',
    '''def _scoped_idempotency_key(request: BusinessExecutionRequest) -> str:
    return scoped_business_idempotency_token(request)
''',
)

replace_once(
    "security/secret_vault.py",
    '''from security.key_provider import (
    InMemoryKeyProvider,
    KeyProvider,
''',
    '''from security.key_provider import (
    FileKeyProvider,
    InMemoryKeyProvider,
    KeyProvider,
''',
)

replace_once(
    "security/secret_vault.py",
    '''def _deserialize_secret_record(payload: dict[str, object]) -> SecretRecord:
''',
    '''def _serialize_key_record(record) -> dict[str, object]:
    from security.key_provider import _serialize_record

    return _serialize_record(record)


def _deserialize_key_record(payload: dict[str, object]):
    from security.key_provider import _deserialize_record

    return _deserialize_record(payload)


def _deserialize_secret_record(payload: dict[str, object]) -> SecretRecord:
''',
)

replace_once(
    "security/secret_vault.py",
    '''        self._root_dir = Path(root_dir)
        self._root_dir.mkdir(parents=True, exist_ok=True)
        super().__init__(policy=policy, key_provider=key_provider)
        self._load_records()
''',
    '''        self._root_dir = Path(root_dir)
        self._root_dir.mkdir(parents=True, exist_ok=True)
        resolved_key_provider = key_provider or FileKeyProvider(
            path=self._root_dir / "key_provider.json"
        )
        super().__init__(policy=policy, key_provider=resolved_key_provider)
        self._load_records()
''',
)

replace_once(
    "security/secret_vault_support.py",
    "from security.key_provider import InMemoryKeyProvider, KeyProvider\n",
    "from security.key_provider import FileKeyProvider, InMemoryKeyProvider, KeyProvider\n",
)

replace_once(
    "security/secret_vault_support.py",
    '''        self._root_dir = Path(root_dir)
        self._root_dir.mkdir(parents=True, exist_ok=True)
        super().__init__(policy=policy, key_provider=key_provider)
        self._load_records()
''',
    '''        self._root_dir = Path(root_dir)
        self._root_dir.mkdir(parents=True, exist_ok=True)
        resolved_key_provider = key_provider or FileKeyProvider(
            path=self._root_dir / "key_provider.json"
        )
        super().__init__(policy=policy, key_provider=resolved_key_provider)
        self._load_records()
''',
)

replace_once(
    "runtime/business_autonomy/bootstrap.py",
    "raise KeyError(f'business is not onboarded for tenant: {tenant_id}:{scoped_business_id}')",
    "raise KeyError(f'business is not explicitly onboarded for tenant: {tenant_id}:{scoped_business_id}')",
)
