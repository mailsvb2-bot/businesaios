import { spawnSync } from "node:child_process";
import { realpathSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const frontendRoot = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const repositoryRoot = resolve(frontendRoot, "..");
const canonicalProductionRoot = "/opt/businesaios";
const productionCheckout = realpathSync(repositoryRoot) === canonicalProductionRoot;

let expectedSha = process.env.EXPECTED_SHA;
if (productionCheckout && !expectedSha) {
  const resolvedHead = spawnSync("git", ["rev-parse", "HEAD"], {
    cwd: repositoryRoot,
    encoding: "utf8",
    stdio: ["ignore", "pipe", "inherit"],
  });
  if (resolvedHead.error || resolvedHead.status !== 0) {
    throw resolvedHead.error ?? new Error("failed to resolve production checkout HEAD");
  }
  expectedSha = resolvedHead.stdout.trim().toLowerCase();
  if (!/^[0-9a-f]{40}$/.test(expectedSha)) {
    throw new Error("production checkout HEAD is not a full git SHA");
  }
}

const command = productionCheckout
  ? resolve(repositoryRoot, ".venv", "bin", "python")
  : process.execPath;
const args = productionCheckout
  ? ["-m", "scripts.server.import_ci_frontend_artifact"]
  : [resolve(frontendRoot, "node_modules", "vite", "bin", "vite.js"), "build"];
const cwd = productionCheckout ? repositoryRoot : frontendRoot;
const env = productionCheckout
  ? {
      ...process.env,
      BUSINESAIOS_ALLOW_NETWORK: "1",
      EXPECTED_SHA: expectedSha,
    }
  : process.env;

const result = spawnSync(command, args, { cwd, env, stdio: "inherit" });
if (result.error) {
  throw result.error;
}
process.exit(result.status ?? 1);
