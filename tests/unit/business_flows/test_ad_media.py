import pytest

from application.business_flows import ad_media as m

JPG = b"\xff\xd8\xff" + b"x" * 100


def apply(facts, assets_facts):
    assets_facts.extend(facts)
    return m.replay(assets_facts)


def test_image_upload_once_and_reuse_same_bytes():
    log: list = []
    calls = []
    a, facts = m.attach_image({}, "j1", JPG, uploader=lambda k, p, n: calls.append(k) or "h1", connection_id="c")
    assets = apply(facts, log)
    assert a is None and assets["j1"].state == "ready" and assets["j1"].image_hash == "h1"
    again, facts2 = m.attach_image(assets, "j1", JPG, uploader=lambda *x: calls.append("2") or "h2")
    assert again.image_hash == "h1" and facts2 == [] and calls == ["image"]


def test_provider_failure_is_ambiguous_and_blocks_retry():
    def boom(*a):
        raise RuntimeError("timeout")

    assets = apply(m.attach_image({}, "j", JPG, uploader=boom)[1], log := [])
    assert assets["j"].state == "ambiguous"
    with pytest.raises(m.AssetError, match="ambiguous"):
        m.attach_image(assets, "j", JPG)
    assert log  # nothing removed


def test_validation_and_default_dry_run():
    with pytest.raises(m.AssetError):
        m.attach_image({}, "j", b"not an image")
    with pytest.raises(m.AssetError):
        m.attach_video({}, "j", b"v", content_type="video/mp4", name="a.mp4", duration_seconds=3)
    with pytest.raises(m.AssetError):
        m.attach_video({}, "j", b"v", content_type="text/plain", name="a.txt", duration_seconds=10)
    _, facts = m.attach_video({}, "j", b"v" * 10, content_type="video/webm", name="clip", duration_seconds=10)
    assert facts[1]["video_id"].startswith("dryrun:") and facts[0]["name"] == "clip"


def test_reuse_remove_and_provider_ids():
    log: list = []
    assets = apply(m.attach_image({}, "j1", JPG, uploader=lambda *a: "h", connection_id="c")[1], log)
    assert [x.job_id for x in m.reusable_images(assets, connection_id="c", exclude_job="j2")] == ["j1"]
    assets = apply(m.reuse_image(assets, "j1", "j2"), log)
    assert assets["j2"].image_hash == "h"
    assets = apply([m.provider_ids("j2", creative_id="cr")], log)
    assert assets["j2"].creative_id == "cr"
    assets = apply([m.remove(assets, "j2")], log)
    assert "j2" not in assets and m.remove(assets, "j2") is None


def test_attach_file_rejects_symlink(tmp_path):
    f = tmp_path / "a.jpg"
    f.write_bytes(JPG)
    (tmp_path / "l.jpg").symlink_to(f)
    with pytest.raises(m.AssetError):
        m.attach_image_file({}, "j", tmp_path / "l.jpg")
    assert m.attach_image_file({}, "j", f)[1][0]["name"] == "a.jpg"


def test_normalize_image_with_optional_pillow():
    import io

    pil = pytest.importorskip("PIL.Image")
    buf = io.BytesIO()
    pil.new("RGB", (300, 100), "red").save(buf, format="PNG")
    out = m.normalize_image(buf.getvalue())
    with pil.open(io.BytesIO(out)) as img:
        assert img.size == (1080, 1080) and img.format == "JPEG"
    with pytest.raises(m.AssetError):
        m.normalize_image(b"\x89PNGbroken")
