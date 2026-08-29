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


def test_frontend_build_emits_exact_sha_bound_release_manifest() -> None:
    package = (ROOT / "frontend/package.json").read_text(encoding="utf-8")
    generator = (ROOT / "frontend/scripts/generate-release-manifest.mjs").read_text(encoding="utf-8")

    assert '"postbuild": "node scripts/generate-release-manifest.mjs"' in package
    for token in (
        "release-manifest.json",
        "BAIOS_CI_TARGET_SHA",
        "BAIOS_FRONTEND_RELEASE_SHA",
        '"rev-parse", "HEAD"',
        '"status", "--porcelain", "--untracked-files=all", "--", "frontend"',
        "frontend source tree must be clean before release manifest generation",
        'createHash("sha256")',
        "path.relative(distDir, absolute)",
        "manifestFiles[relative]",
        "frontend release SHA ${envSha} does not match git HEAD ${gitSha}",
        "exact frontend release SHA is unavailable",
    ):
        assert token in generator


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
