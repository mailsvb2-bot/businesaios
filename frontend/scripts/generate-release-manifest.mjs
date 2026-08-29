import { createHash } from "node:crypto";
import { execFileSync } from "node:child_process";
import { readdir, readFile, writeFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const scriptDir = path.dirname(fileURLToPath(import.meta.url));
const frontendDir = path.resolve(scriptDir, "..");
const rootDir = path.resolve(frontendDir, "..");
const distDir = path.join(frontendDir, "dist");
const manifestPath = path.join(distDir, "release-manifest.json");
const shaPattern = /^[0-9a-f]{40}$/;

function normalizeSha(value, source) {
  const sha = String(value ?? "").trim().toLowerCase();
  if (!shaPattern.test(sha)) {
    throw new Error(`${source} must be an exact 40-character git SHA`);
  }
  return sha;
}

function readGitHead() {
  try {
    return normalizeSha(
      execFileSync("git", ["-C", rootDir, "rev-parse", "HEAD"], {
        encoding: "utf8",
        stdio: ["ignore", "pipe", "ignore"],
      }),
      "git HEAD",
    );
  } catch (error) {
    if (error instanceof Error && error.message.includes("git HEAD")) {
      throw error;
    }
    return null;
  }
}

function resolveCommitSha() {
  const ciSha = process.env.BAIOS_CI_TARGET_SHA
    ? normalizeSha(process.env.BAIOS_CI_TARGET_SHA, "BAIOS_CI_TARGET_SHA")
    : null;
  const releaseSha = process.env.BAIOS_FRONTEND_RELEASE_SHA
    ? normalizeSha(process.env.BAIOS_FRONTEND_RELEASE_SHA, "BAIOS_FRONTEND_RELEASE_SHA")
    : null;
  if (ciSha && releaseSha && ciSha !== releaseSha) {
    throw new Error(`BAIOS_CI_TARGET_SHA ${ciSha} does not match BAIOS_FRONTEND_RELEASE_SHA ${releaseSha}`);
  }

  const envSha = ciSha || releaseSha;
  const gitSha = readGitHead();
  if (envSha && gitSha && envSha !== gitSha) {
    throw new Error(`frontend release SHA ${envSha} does not match git HEAD ${gitSha}`);
  }
  if (envSha) {
    return envSha;
  }
  if (gitSha) {
    return gitSha;
  }
  throw new Error(
    "exact frontend release SHA is unavailable; set BAIOS_FRONTEND_RELEASE_SHA or build from a git checkout",
  );
}

async function collectFiles(directory) {
  const entries = await readdir(directory, { withFileTypes: true });
  const files = [];
  for (const entry of entries) {
    const absolute = path.join(directory, entry.name);
    if (entry.isDirectory()) {
      files.push(...(await collectFiles(absolute)));
    } else if (entry.isFile() && absolute !== manifestPath) {
      files.push(absolute);
    }
  }
  return files;
}

const commitSha = resolveCommitSha();
const files = (await collectFiles(distDir)).sort((left, right) => left.localeCompare(right));
const manifestFiles = {};
for (const absolute of files) {
  const relative = path.relative(distDir, absolute).split(path.sep).join("/");
  manifestFiles[relative] = createHash("sha256").update(await readFile(absolute)).digest("hex");
}

if (!("index.html" in manifestFiles) || !Object.keys(manifestFiles).some((name) => name.startsWith("assets/"))) {
  throw new Error("frontend release manifest must cover index.html and at least one asset");
}

const manifest = {
  schema_version: 1,
  commit_sha: commitSha,
  files: manifestFiles,
};
await writeFile(manifestPath, `${JSON.stringify(manifest)}\n`, "utf8");
console.log(`wrote ${manifestPath} for ${commitSha} with ${Object.keys(manifestFiles).length} file(s)`);
