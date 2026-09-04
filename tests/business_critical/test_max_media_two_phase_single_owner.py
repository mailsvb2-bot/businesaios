from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import runtime.business_autonomy.provider_max_media_http as max_media_http
from application.business_autonomy.provider_catalog import provider_map
from runtime.business_autonomy.provider_max_media_http import execute_max_media_message
from runtime.business_autonomy.provider_media import (
    ProviderMediaPreparationCoordinator,
    provider_media_file_digest,
)
from runtime.business_autonomy.provider_transport_bindings import ProviderTransportBindings
from runtime.platform.business_autonomy_sqlite_distributed_state import (
    SQLiteDistributedCompareAndSwap,
    SQLiteStateDatabase,
)

_MAX_BASE_URL = ProviderTransportBindings().describe(provider_map()["max_messaging"])["base_url"]


def _coordinator(path: Path) -> ProviderMediaPreparationCoordinator:
    database = SQLiteStateDatabase(path)
    return ProviderMediaPreparationCoordinator(
        SQLiteDistributedCompareAndSwap(database, scope="test-provider-media")
    )


def _http_result(status: int, payload: dict) -> SimpleNamespace:
    return SimpleNamespace(
        status=status,
        json=payload,
        text=__import__("json").dumps(payload),
        headers={},
        error_kind=None,
        error_message=None,
    )


def test_prepared_media_state_is_durable_and_does_not_expose_token_or_path(tmp_path: Path) -> None:
    source = tmp_path / "private-audio.ogg"
    source.write_bytes(b"audio-payload")
    digest = provider_media_file_digest(source)
    first = _coordinator(tmp_path / "state.sqlite3")
    prepared = first.store_prepared(
        tenant_id="tenant-a",
        business_id="business-a",
        provider_key="max_messaging",
        job_id="provider-job-1",
        media_type="audio",
        source_digest=digest,
        remote_token="secret-media-token",
    )
    assert "secret-media-token" not in repr(prepared)
    assert str(source) not in prepared.state_key

    second = _coordinator(tmp_path / "state.sqlite3")
    restored = second.read(
        tenant_id="tenant-a",
        business_id="business-a",
        provider_key="max_messaging",
        job_id="provider-job-1",
        media_type="audio",
        source_digest=digest,
    )
    assert restored is not None and restored.remote_token == "secret-media-token"


def test_max_media_prepare_happens_before_any_final_message_write(tmp_path: Path, monkeypatch) -> None:
    source = tmp_path / "audio.ogg"
    source.write_bytes(b"audio-payload")
    calls: list[str] = []

    def fake_request(**kwargs):
        url = str(kwargs["url"])
        calls.append(url)
        if "/uploads?type=audio" in url:
            return _http_result(200, {"url": "https://upload.max.ru/audio"})
        raise AssertionError("final MAX message write must not run during prepare phase")

    monkeypatch.setattr(max_media_http, "_sync_request", fake_request)
    monkeypatch.setattr(
        max_media_http,
        "_sync_multipart_file",
        lambda **_kwargs: _http_result(200, {"token": "prepared-token-1"}),
    )
    coordinator = _coordinator(tmp_path / "state.sqlite3")
    result = execute_max_media_message(
        tenant_id="tenant-a",
        business_id="business-a",
        queue_job_id="provider-job-1",
        payload={"user_id": "77", "text": "caption", "attachments": [{"kind": "audio", "source": str(source)}]},
        access_token="provider-secret",
        media_preparation=coordinator,
        timeout_seconds=10,
        provider_base_url=_MAX_BASE_URL,
    )
    assert result is not None
    assert result["parsed_response"]["error_category"] == "media_preparation"
    assert calls == [f"{_MAX_BASE_URL}/uploads?type=audio"]
    assert "prepared-token-1" not in repr(result)
    digest = provider_media_file_digest(source)
    assert coordinator.read(
        tenant_id="tenant-a",
        business_id="business-a",
        provider_key="max_messaging",
        job_id="provider-job-1",
        media_type="audio",
        source_digest=digest,
    ) is not None


def test_second_max_media_attempt_performs_exactly_one_final_write_with_prepared_token(tmp_path: Path, monkeypatch) -> None:
    source = tmp_path / "audio.ogg"
    source.write_bytes(b"audio-payload")
    coordinator = _coordinator(tmp_path / "state.sqlite3")
    digest = provider_media_file_digest(source)
    coordinator.store_prepared(
        tenant_id="tenant-a",
        business_id="business-a",
        provider_key="max_messaging",
        job_id="provider-job-1",
        media_type="audio",
        source_digest=digest,
        remote_token="prepared-token-1",
    )
    calls: list[dict] = []

    def fake_request(**kwargs):
        calls.append(dict(kwargs))
        assert "/messages?user_id=77" in str(kwargs["url"])
        return _http_result(200, {"message": {"id": "max-message-1"}})

    monkeypatch.setattr(max_media_http, "_sync_request", fake_request)
    monkeypatch.setattr(
        max_media_http,
        "_sync_multipart_file",
        lambda **_kwargs: (_ for _ in ()).throw(AssertionError("prepared token must skip upload")),
    )
    result = execute_max_media_message(
        tenant_id="tenant-a",
        business_id="business-a",
        queue_job_id="provider-job-1",
        payload={"user_id": "77", "text": "caption", "attachments": [{"kind": "audio", "source": str(source)}]},
        access_token="provider-secret",
        media_preparation=coordinator,
        timeout_seconds=10,
        provider_base_url=_MAX_BASE_URL,
    )
    assert result is not None and result["http_status"] == 200
    assert len(calls) == 1
    body = __import__("json").loads(calls[0]["body"].decode("utf-8"))
    assert body["attachments"] == [{"type": "audio", "payload": {"token": "prepared-token-1"}}]
    assert result["request"]["json_body"]["attachments"][0]["payload"]["token"] == "***"


def test_explicit_max_media_token_rejection_invalidates_prepared_state(tmp_path: Path, monkeypatch) -> None:
    source = tmp_path / "audio.ogg"
    source.write_bytes(b"audio-payload")
    coordinator = _coordinator(tmp_path / "state.sqlite3")
    digest = provider_media_file_digest(source)
    coordinator.store_prepared(
        tenant_id="tenant-a",
        business_id="business-a",
        provider_key="max_messaging",
        job_id="provider-job-1",
        media_type="audio",
        source_digest=digest,
        remote_token="prepared-token-1",
    )
    monkeypatch.setattr(
        max_media_http,
        "_sync_request",
        lambda **_kwargs: _http_result(200, {"code": "invalid_token", "message": "invalid attachment token"}),
    )
    execute_max_media_message(
        tenant_id="tenant-a",
        business_id="business-a",
        queue_job_id="provider-job-1",
        payload={"user_id": "77", "text": "caption", "attachments": [{"kind": "audio", "source": str(source)}]},
        access_token="provider-secret",
        media_preparation=coordinator,
        timeout_seconds=10,
        provider_base_url=_MAX_BASE_URL,
    )
    assert coordinator.read(
        tenant_id="tenant-a",
        business_id="business-a",
        provider_key="max_messaging",
        job_id="provider-job-1",
        media_type="audio",
        source_digest=digest,
    ) is None


def test_prepared_max_media_finishes_after_local_file_is_removed(tmp_path: Path, monkeypatch) -> None:
    source = tmp_path / "ephemeral.ogg"
    source.write_bytes(b"ephemeral-audio")
    digest = provider_media_file_digest(source)
    coordinator = _coordinator(tmp_path / "state-after-delete.sqlite3")
    coordinator.store_prepared(
        tenant_id="tenant-a", business_id="business-a", provider_key="max_messaging",
        job_id="provider-job-delete", media_type="audio", source_digest=digest,
        remote_token="prepared-token-delete",
    )
    source.unlink()
    calls: list[dict] = []

    def fake_request(**kwargs):
        calls.append(dict(kwargs))
        return _http_result(200, {"message": {"id": "max-message-delete"}})

    monkeypatch.setattr(max_media_http, "_sync_request", fake_request)
    monkeypatch.setattr(
        max_media_http, "_sync_multipart_file",
        lambda **_kwargs: (_ for _ in ()).throw(AssertionError("prepared token must not reopen local file")),
    )
    result = execute_max_media_message(
        tenant_id="tenant-a", business_id="business-a", queue_job_id="provider-job-delete",
        payload={"user_id": "77", "text": "caption", "attachments": [{"kind": "voice", "source": str(source), "source_digest": digest}]},
        access_token="provider-secret", media_preparation=coordinator, timeout_seconds=10,
        provider_base_url=_MAX_BASE_URL,
    )
    assert result is not None and result["http_status"] == 200
    assert len(calls) == 1
