from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_frontend_release_is_sha_bound_before_publication() -> None:
    bootstrap = (ROOT / "scripts/server/bootstrap_and_verify_production.sh").read_text(encoding="utf-8")
    ci = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")

    for token in (
        "release-manifest.json",
        '"commit_sha": sha',
        "hashlib.sha256",
        'BAIOS_FRONTEND_SHA="$BAIOS_CI_TARGET_SHA"',
    ):
        assert token in ci
    for token in (
        'FRONTEND_MANIFEST="$FRONTEND_DIST/release-manifest.json"',
        "frontend release manifest commit_sha does not match EXPECTED_SHA",
        "frontend dist files do not exactly match release manifest",
        "frontend manifest hash mismatch",
    ):
        assert token in bootstrap
    assert bootstrap.index("frontend release manifest commit_sha does not match EXPECTED_SHA") < bootstrap.index(
        'find "$FRONTEND_DIST" -type d -exec chmod 0755'
    )


def test_production_frontend_wrapper_derives_expected_sha_from_checkout() -> None:
    wrapper = (ROOT / "frontend/scripts/build-production-safe.mjs").read_text(encoding="utf-8")

    for token in (
        "let expectedSha = process.env.EXPECTED_SHA;",
        "if (productionCheckout && !expectedSha)",
        'spawnSync("git", ["rev-parse", "HEAD"]',
        "expectedSha = resolvedHead.stdout.trim().toLowerCase();",
        '/^[0-9a-f]{40}$/.test(expectedSha)',
        "EXPECTED_SHA: expectedSha",
    ):
        assert token in wrapper
    assert wrapper.index('spawnSync("git", ["rev-parse", "HEAD"]') < wrapper.index("EXPECTED_SHA: expectedSha")


def test_public_frontend_verifier_fetches_and_hashes_entry_assets() -> None:
    verifier = (ROOT / "scripts/server/verify_runtime_host_contract.sh").read_text(encoding="utf-8")

    for token in (
        'curl -fsS "$PUBLIC_APP_BASE/release-manifest.json"',
        "HTMLParser",
        "urlopen(url, timeout=10)",
        "public frontend index.html does not match release manifest",
        "public frontend asset hash mismatch",
        "frontend entry asset is not covered by release manifest",
    ):
        assert token in verifier
