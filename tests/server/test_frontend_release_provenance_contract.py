import shutil
import subprocess
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


def test_production_frontend_wrapper_executes_fail_closed_sha_fallback() -> None:
    node = shutil.which("node")
    assert node is not None, "Node.js is required to verify the production frontend wrapper"
    wrapper_uri = (ROOT / "frontend/scripts/build-production-safe.mjs").as_uri()
    probe = f"""
import assert from "node:assert/strict";
import {{ runBuildProductionSafe }} from {wrapper_uri!r};

const validSha = "a".repeat(40);
const calls = [];
const status = runBuildProductionSafe({{
  environment: {{}},
  resolvedRepositoryRoot: "/opt/businesaios",
  canonicalRoot: "/opt/businesaios",
  repositoryPath: "/opt/businesaios",
  frontendPath: "/unused/frontend",
  runtimeExecPath: "/unused/node",
  runCommand(command, args, options) {{
    calls.push({{ command, args, options }});
    if (command === "git") {{
      return {{ status: 0, stdout: `${{validSha}}\\n` }};
    }}
    return {{ status: 0 }};
  }},
}});
assert.equal(status, 0);
assert.equal(calls.length, 2);
assert.equal(calls[0].command, "git");
assert.deepEqual(calls[0].args, ["rev-parse", "HEAD"]);
assert.equal(calls[1].command, "/opt/businesaios/.venv/bin/python");
assert.deepEqual(calls[1].args, ["-m", "scripts.server.import_ci_frontend_artifact"]);
assert.equal(calls[1].options.env.EXPECTED_SHA, validSha);
assert.equal(calls[1].options.env.BUSINESAIOS_ALLOW_NETWORK, "1");

const suppliedCalls = [];
const suppliedStatus = runBuildProductionSafe({{
  environment: {{ EXPECTED_SHA: `  ${{validSha.toUpperCase()}}  ` }},
  resolvedRepositoryRoot: "/opt/businesaios",
  canonicalRoot: "/opt/businesaios",
  repositoryPath: "/opt/businesaios",
  frontendPath: "/unused/frontend",
  runtimeExecPath: "/unused/node",
  runCommand(command, args, options) {{
    suppliedCalls.push({{ command, args, options }});
    return {{ status: 0 }};
  }},
}});
assert.equal(suppliedStatus, 0);
assert.equal(suppliedCalls.length, 1);
assert.equal(suppliedCalls[0].command, "/opt/businesaios/.venv/bin/python");
assert.equal(suppliedCalls[0].options.env.EXPECTED_SHA, validSha);

let blankCalls = 0;
assert.throws(
  () => runBuildProductionSafe({{
    environment: {{ EXPECTED_SHA: "   " }},
    resolvedRepositoryRoot: "/opt/businesaios",
    canonicalRoot: "/opt/businesaios",
    repositoryPath: "/opt/businesaios",
    frontendPath: "/unused/frontend",
    runtimeExecPath: "/unused/node",
    runCommand() {{
      blankCalls += 1;
      return {{ status: 0 }};
    }},
  }}),
  /production EXPECTED_SHA is not a full git SHA/,
);
assert.equal(blankCalls, 0);

let invalidCalls = 0;
assert.throws(
  () => runBuildProductionSafe({{
    environment: {{}},
    resolvedRepositoryRoot: "/opt/businesaios",
    canonicalRoot: "/opt/businesaios",
    repositoryPath: "/opt/businesaios",
    frontendPath: "/unused/frontend",
    runtimeExecPath: "/unused/node",
    runCommand(command) {{
      invalidCalls += 1;
      assert.equal(command, "git");
      return {{ status: 0, stdout: "not-a-full-sha\\n" }};
    }},
  }}),
  /production checkout HEAD is not a full git SHA/,
);
assert.equal(invalidCalls, 1);
"""
    completed = subprocess.run(
        [node, "--input-type=module", "--eval", probe],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr or completed.stdout


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
