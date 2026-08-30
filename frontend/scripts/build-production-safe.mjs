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
  expectedShaProvided = expectedSha !== undefined,
  repositoryRoot: checkoutRoot,
  runGit = spawnSync,
}) {
  const normalizedExpectedSha =
    typeof expectedSha === "string" ? expectedSha.trim().toLowerCase() : expectedSha;
  if (!productionCheckout || expectedShaProvided) {
    return normalizedExpectedSha;
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

export function runBuildProductionSafe({
  environment = process.env,
  resolvedRepositoryRoot = realpathSync(repositoryRoot),
  canonicalRoot = canonicalProductionRoot,
  repositoryPath = repositoryRoot,
  frontendPath = frontendRoot,
  runtimeExecPath = process.execPath,
  runCommand = spawnSync,
} = {}) {
  const productionCheckout = resolvedRepositoryRoot === canonicalRoot;
  const expectedShaProvided = Object.prototype.hasOwnProperty.call(environment, "EXPECTED_SHA");
  const expectedSha = resolveProductionExpectedSha({
    productionCheckout,
    expectedSha: environment.EXPECTED_SHA,
    expectedShaProvided,
    repositoryRoot: repositoryPath,
    runGit: runCommand,
  });

  const command = productionCheckout
    ? resolve(repositoryPath, ".venv", "bin", "python")
    : runtimeExecPath;
  const args = productionCheckout
    ? ["-m", "scripts.server.import_ci_frontend_artifact"]
    : [resolve(frontendPath, "node_modules", "vite", "bin", "vite.js"), "build"];
  const cwd = productionCheckout ? repositoryPath : frontendPath;
  const env = productionCheckout ? buildProductionImportEnv(environment, expectedSha) : environment;

  const result = runCommand(command, args, { cwd, env, stdio: "inherit" });
  if (result.error) {
    throw result.error;
  }
  return result.status ?? 1;
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  process.exit(runBuildProductionSafe());
}
