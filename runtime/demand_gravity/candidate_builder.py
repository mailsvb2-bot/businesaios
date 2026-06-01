from __future__ import annotations

from datetime import UTC, datetime, timezone
from hashlib import sha256

from runtime.demand_gravity.contracts import CandidateWriteMode, DemandCandidate, DemandChannel, DemandSignal
from runtime.demand_gravity.no_second_brain import assert_payload_has_no_decision_fields
from runtime.demand_gravity.validation import validate_demand_candidate, validate_demand_signal


class DemandSignalCandidateProducer:
    def build_candidates(
        self,
        *,
        tenant_id: str,
        business_id: str,
        signals: tuple[DemandSignal, ...],
        now: datetime | None = None,
        correlation_id: str = "demand-gravity",
    ) -> tuple[DemandCandidate, ...]:
        if not tenant_id.strip():
            raise ValueError("tenant_id_required")
        if not business_id.strip():
            raise ValueError("business_id_required")
        now = now or datetime.now(UTC)
        grouped: dict[DemandChannel, list[DemandSignal]] = {}
        seen_fingerprints: set[str] = set()
        for signal in signals:
            validate_demand_signal(signal)
            if signal.tenant_id != tenant_id:
                raise ValueError("cross_tenant_signal_forbidden")
            if signal.business_id != business_id:
                raise ValueError("cross_business_signal_forbidden")
            if signal.raw_fingerprint in seen_fingerprints:
                continue
            seen_fingerprints.add(signal.raw_fingerprint)
            grouped.setdefault(signal.channel, []).append(signal)

        candidates: list[DemandCandidate] = []
        for channel in sorted(grouped, key=lambda item: item.value):
            channel_signals = tuple(grouped[channel])
            candidate_id = self._candidate_id(tenant_id=tenant_id, business_id=business_id, channel=channel, signals=channel_signals)
            payload = {
                "candidate_type": "demand_signal_cluster",
                "tenant_id": tenant_id,
                "business_id": business_id,
                "channel": channel.value,
                "signal_count": len(channel_signals),
                "normalized_terms": sorted({s.normalized_text for s in channel_signals if s.normalized_text}),
                "source": "demand_gravity",
                "decision_owner": "DecisionCore",
                "execution_allowed": False,
            }
            assert_payload_has_no_decision_fields(payload)
            candidate = DemandCandidate(
                candidate_id=candidate_id,
                tenant_id=tenant_id,
                business_id=business_id,
                channel=channel,
                signal_ids=tuple(s.signal_id for s in channel_signals),
                write_mode=CandidateWriteMode.ADVISORY_ONLY,
                evidence_refs=tuple(s.source_ref for s in channel_signals),
                created_at=now,
                payload=payload,
                idempotency_key=f"demand-gravity:{tenant_id}:{business_id}:{candidate_id}",
                correlation_id=correlation_id,
            )
            validate_demand_candidate(candidate)
            candidates.append(candidate)
        return tuple(candidates)

    @staticmethod
    def _candidate_id(*, tenant_id: str, business_id: str, channel: DemandChannel, signals: tuple[DemandSignal, ...]) -> str:
        raw = "|".join([tenant_id, business_id, channel.value, *sorted(s.raw_fingerprint for s in signals)]).encode()
        return f"dgc_{sha256(raw).hexdigest()[:32]}"


DemandCandidateBuilder = DemandSignalCandidateProducer
