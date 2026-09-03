from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import runtime.business_autonomy.provider_vk_media_http as vk_media_http
from application.business_autonomy.provider_catalog import provider_map
from runtime.business_autonomy.provider_media import (
    ProviderMediaPreparationCoordinator,
    provider_media_file_digest,
)
from runtime.business_autonomy.provider_transport_bindings import ProviderTransportBindings
from runtime.business_autonomy.provider_vk_media_http import prepare_vk_audio_attachment
from runtime.platform.business_autonomy_sqlite_distributed_state import (
    SQLiteDistributedCompareAndSwap,
    SQLiteStateDatabase,
)

_VK_BASE_URL = ProviderTransportBindings().describe(provider_map()["vk_messaging"])["base_url"]


def _coordinator(path: Path) -> ProviderMediaPreparationCoordinator:
    database = SQLiteStateDatabase(path)
    return ProviderMediaPreparationCoordinator(
        SQLiteDistributedCompareAndSwap(database, scope="test-vk-media")
    )


def _http_result(payload: dict) -> SimpleNamespace:
    return SimpleNamespace(
        status=200,
        json=payload,
        text="",
        headers={},
        error_kind=None,
        error_message=None,
    )


def test_vk_audio_prepares_provider_attachment_once_and_reuses_it(tmp_path: Path, monkeypatch) -> None:
    source = tmp_path / "voice.ogg"
    source.write_bytes(b"voice")
    calls: list[str] = []

    def fake_vk_call(*, method, **_kwargs):
        calls.append(method)
        if method == "docs.getMessagesUploadServer":
            return {"response": {"upload_url": "https://upload.vk.com/doc"}}
        if method == "docs.save":
            return {"response": {"audio_message": {"owner_id": 11, "id": 22, "access_key": "key"}}}
        raise AssertionError(method)

    monkeypatch.setattr(vk_media_http, "_vk_call", fake_vk_call)
    monkeypatch.setattr(
        vk_media_http,
        "_sync_multipart_file",
        lambda **_kwargs: _http_result({"file": "upload-file-token"}),
    )
    coordinator = _coordinator(tmp_path / "state.sqlite3")
    kwargs = dict(
        tenant_id="tenant-a", business_id="business-a", queue_job_id="job-1",
        peer_id="77", payload={"attachments": [{"kind": "voice", "source": str(source)}]},
        access_token="provider-secret", media_preparation=coordinator, timeout_seconds=10, provider_base_url=_VK_BASE_URL,
    )
    first = prepare_vk_audio_attachment(**kwargs)
    second = prepare_vk_audio_attachment(**kwargs)

    assert first == "doc11_22_key" and second == first
    assert calls == ["docs.getMessagesUploadServer", "docs.save"]


def test_vk_non_ogg_audio_uses_document_upload_type(tmp_path: Path, monkeypatch) -> None:
    source = tmp_path / "audio.mp3"
    source.write_bytes(b"mp3")
    upload_types: list[str] = []

    def fake_vk_call(*, method, params, **_kwargs):
        if method == "docs.getMessagesUploadServer":
            upload_types.append(str(params["type"]))
            return {"response": {"upload_url": "https://upload.vk.com/doc"}}
        return {"response": {"doc": {"owner_id": 1, "id": 2}}}

    monkeypatch.setattr(vk_media_http, "_vk_call", fake_vk_call)
    monkeypatch.setattr(
        vk_media_http,
        "_sync_multipart_file",
        lambda **_kwargs: _http_result({"file": "upload-file-token"}),
    )
    result = prepare_vk_audio_attachment(
        tenant_id="tenant-a",
        business_id="business-a",
        queue_job_id="job-2",
        peer_id="77",
        payload={"attachments": [{"kind": "audio", "source": str(source)}]},
        access_token="provider-secret",
        media_preparation=_coordinator(tmp_path / "state.sqlite3"),
        timeout_seconds=10,
        provider_base_url=_VK_BASE_URL,
    )

    assert result == "doc1_2"
    assert upload_types == ["doc"]


def test_vk_media_requires_durable_queue_identity(tmp_path: Path) -> None:
    source = tmp_path / "voice.ogg"
    source.write_bytes(b"voice")
    try:
        prepare_vk_audio_attachment(
            tenant_id="tenant-a", business_id="business-a", queue_job_id="",
            peer_id="77", payload={"attachments": [{"kind": "voice", "source": str(source)}]},
            access_token="provider-secret", media_preparation=_coordinator(tmp_path / "state.sqlite3"),
            timeout_seconds=10,
            provider_base_url=_VK_BASE_URL,
        )
    except ValueError as exc:
        assert "durable queue job identity" in str(exc)
    else:
        raise AssertionError("VK media without durable queue identity must fail closed")


def test_prepared_vk_media_reuses_attachment_after_local_file_is_removed(tmp_path: Path, monkeypatch) -> None:
    source = tmp_path / "ephemeral-voice.ogg"
    source.write_bytes(b"ephemeral-voice")
    digest = provider_media_file_digest(source)
    coordinator = _coordinator(tmp_path / "state-after-delete.sqlite3")
    coordinator.store_prepared(
        tenant_id="tenant-a", business_id="business-a", provider_key="vk_messaging",
        job_id="job-delete", media_type="audio:audio_message", source_digest=digest,
        remote_token="doc11_22_key",
    )
    source.unlink()
    monkeypatch.setattr(
        vk_media_http, "_vk_call",
        lambda **_kwargs: (_ for _ in ()).throw(AssertionError("prepared VK attachment must skip provider upload API")),
    )
    monkeypatch.setattr(
        vk_media_http, "_sync_multipart_file",
        lambda **_kwargs: (_ for _ in ()).throw(AssertionError("prepared VK attachment must skip local file upload")),
    )
    attachment = prepare_vk_audio_attachment(
        tenant_id="tenant-a", business_id="business-a", queue_job_id="job-delete", peer_id="77",
        payload={"attachments": [{"kind": "voice", "source": str(source), "source_digest": digest}]},
        access_token="provider-secret", media_preparation=coordinator, timeout_seconds=10,
        provider_base_url=_VK_BASE_URL,
    )
    assert attachment == "doc11_22_key"
