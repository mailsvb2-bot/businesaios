import { spawnSync } from "node:child_process";
import { realpathSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const frontendRoot = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const repositoryRoot = resolve(frontendRoot, "..");
const canonicalProductionRoot = "/opt/businesaios";

export function resolveProductionExpectedSha({
  productionCheckout,
  expectedSha,
  repositoryRoot: checkoutRoot,
  runGit = spawnSync,
}) {
  if (!productionCheckout || expectedSha) {
    return expectedSha;
  }

  const resolvedHead = runGit("git", ["rev-parse", "HEAD"], {
    cwd: checkoutRoot,
    encoding: "utf8",
    stdio: ["ignore", "pipe", "inherit"],
  });
  if (resolvedHead.error || resolvedHead.status !== 0) {
    throw resolvedHead.error ?? new Error("failed to resolve production checkout HEAD");
  }

  const checkoutSha = resolvedHead.stdout.trim().toLowerCase();
  if (!/^[0-9a-f]{40}$/.test(checkoutSha)) {
    throw new Error("production checkout HEAD is not a full git SHA");
  }
  return checkoutSha;
}

export function buildProductionImportEnv(baseEnv, expectedSha) {
  if (!expectedSha || !/^[0-9a-f]{40}$/.test(expectedSha)) {
    throw new Error("production EXPECTED_SHA is not a full git SHA");
  }
  return {
    ...baseEnv,
    BUSINESAIOS_ALLOW_NETWORK: "1",
    EXPECTED_SHA: expectedSha,
  };
}

function main() {
  const productionCheckout = realpathSync(repositoryRoot) === canonicalProductionRoot;
  const expectedSha = resolveProductionExpectedSha({
    productionCheckout,
    expectedSha: process.env.EXPECTED_SHA,
    repositoryRoot,
  });

  const command = productionCheckout
    ? resolve(repositoryRoot, ".venv", "bin", "python")
    : process.execPath;
  const args = productionCheckout
    ? ["-m", "scripts.server.import_ci_frontend_artifact"]
    : [resolve(frontendRoot, "node_modules", "vite", "bin", "vite.js"), "build"];
  const cwd = productionCheckout ? repositoryRoot : frontendRoot;
  const env = productionCheckout ? buildProductionImportEnv(process.env, expectedSha) : process.env;

  const result = spawnSync(command, args, { cwd, env, stdio: "inherit" });
  if (result.error) {
    throw result.error;
  }
  process.exit(result.status ?? 1);
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  main();
}
