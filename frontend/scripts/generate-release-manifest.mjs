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
  if (!shaPattern.test(sha)) throw new Error(`${source} must be an exact 40-character git SHA`);
  return sha;
}

function readGitHead() {
  return normalizeSha(execFileSync("git", ["-C", rootDir, "rev-parse", "HEAD"], { encoding: "utf8" }), "git HEAD");
}

async function collectFiles(directory) {
  const entries = await readdir(directory, { withFileTypes: true });
  const files = [];
  for (const entry of entries) {
    const absolute = path.join(directory, entry.name);
    if (entry.isDirectory()) files.push(...(await collectFiles(absolute)));
    else if (entry.isFile() && absolute !== manifestPath) files.push(absolute);
  }
  return files;
}

const commitSha = readGitHead();
const manifestFiles = {};
for (const absolute of (await collectFiles(distDir)).sort()) {
  const relative = path.relative(distDir, absolute).split(path.sep).join("/");
  manifestFiles[relative] = createHash("sha256").update(await readFile(absolute)).digest("hex");
}

if (!("index.html" in manifestFiles)) throw new Error("frontend manifest requires index.html");

await writeFile(manifestPath, `${JSON.stringify({ schema_version: 1, commit_sha: commitSha, files: manifestFiles })}\n`, "utf8");
console.log(`wrote ${manifestPath} for ${commitSha}`);
