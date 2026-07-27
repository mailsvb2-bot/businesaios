from pathlib import Path

from core.retention.engine import evaluate_for_day
from runtime.platform.event_store.sqlite_event_store import SqliteEventStore


def test_retention_tables_created(tmp_path: Path):
    db_path = tmp_path / "events.db"
    with SqliteEventStore(str(db_path)) as store:
        store.upsert_user_features_daily(
            tenant_id="t1",
            user_id="u1",
            day_key="2026-02-25",
            features_json="{}",
            created_at_ms=123,
        )
        assert store.get_user_features_daily(tenant_id="t1", user_id="u1", day_key="2026-02-25") is not None


def test_retention_decision_flow(tmp_path: Path):
    db_path = tmp_path / "events.db"
    with SqliteEventStore(str(db_path)) as store:
        # Minimal events for the day (use canonical envelope expected by event store)
        store.append_event(
            {
                "event_id": "e1",
                "tenant_id": "t1",
                "user_id": "u1",
                "source": "test",
                "event_type": "mood_logged",
                "timestamp_ms": 1700000000000,
                "payload": {"mood": 2},
            }
        )
        store.append_event(
            {
                "event_id": "e2",
                "tenant_id": "t1",
                "user_id": "u1",
                "source": "test",
                "event_type": "audio_sent",
                "timestamp_ms": 1700000100000,
                "payload": {"audio_id": "a1"},
            }
        )

        evaluation = evaluate_for_day(
            store,
            tenant_id="t1",
            user_id="u1",
            day_key="2023-11-14",  # matches timestamps above (approx UTC)
            day_index=20,
            now_ms=1700000200000,
            outbound_telemetry={"qsize": 0, "telegram_api_latency_p90_ms": 0},
        )

        assert 0.0 <= evaluation.hazard <= 1.0
        assert 0.0 <= evaluation.readiness <= 1.0
        assert evaluation.debug["no_second_brain"] is True
        assert all(candidate.candidate_id for candidate in evaluation.candidates)

        raw = store.get_user_features_daily(
            tenant_id="t1",
            user_id="u1",
            day_key=evaluation.day_key,
        )
        assert raw is None
