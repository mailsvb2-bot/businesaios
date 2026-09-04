from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from runtime._internal.http_transport import (
    DisabledNetworkTransport,
    _upload_target,
    sync_multipart_file,
)


def test_disabled_network_transport_blocks_multipart(tmp_path: Path) -> None:
    source = tmp_path / "audio.ogg"
    source.write_bytes(b"audio")

    with pytest.raises(RuntimeError, match="network_disabled_in_this_runtime"):
        asyncio.run(
            DisabledNetworkTransport().post_multipart_file(
                url="https://upload.example/media",
                path=source,
                field_name="audio",
            )
        )


def test_multipart_upload_target_rejects_cleartext_and_local_networks() -> None:
    for url in (
        "http://upload.example/media",
        "https://localhost/media",
        "https://127.0.0.1/media",
        "https://10.0.0.7/media",
        "https://user:password@upload.example/media",
    ):
        with pytest.raises(ValueError):
            _upload_target(url)


def test_multipart_missing_file_fails_before_network(tmp_path: Path) -> None:
    missing = tmp_path / "missing.ogg"
    with pytest.raises(FileNotFoundError):
        sync_multipart_file(
            url="https://upload.example/media",
            path=missing,
            field_name="audio",
        )
