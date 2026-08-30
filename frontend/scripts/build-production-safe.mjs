import { spawnSync } from "node:child_process";
import { realpathSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const frontendRoot = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const repositoryRoot = resolve(frontendRoot, "..");
const canonicalProductionRoot = "/opt/businesaios";
const productionCheckout = realpathSync(repositoryRoot) === canonicalProductionRoot;

const command = productionCheckout
  ? resolve(repositoryRoot, ".venv", "bin", "python")
  : process.execPath;
const args = productionCheckout
  ? ["-m", "scripts.server.import_ci_frontend_artifact"]
  : [resolve(frontendRoot, "node_modules", "vite", "bin", "vite.js"), "build"];
const cwd = productionCheckout ? repositoryRoot : frontendRoot;
const env = productionCheckout
  ? { ...process.env, BUSINESAIOS_ALLOW_NETWORK: "1" }
  : process.env;

const stdio = productionCheckout
  ? ["inherit", "inherit", "inherit", ...Array(6).fill("ignore"), 9]
  : "inherit";
const result = spawnSync(command, args, { cwd, env, stdio });
if (result.error) {
  throw result.error;
}
process.exit(result.status ?? 1);
