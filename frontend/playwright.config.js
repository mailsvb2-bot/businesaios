import { defineConfig, devices } from "@playwright/test";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";

const repoRoot = path.resolve("..");
const artifacts = path.join(repoRoot, "artifacts", "ci", "browser-e2e");
const runtimeRoot = process.env.BAIOS_E2E_RUNTIME_DIR || path.join(os.tmpdir(), `businessaios-browser-e2e-${process.pid}`);
const apiPort = process.env.BAIOS_E2E_API_PORT || "8765";
const uiPort = process.env.BAIOS_E2E_UI_PORT || "4173";
const apiTarget = `http://127.0.0.1:${apiPort}`;
const uiTarget = `http://127.0.0.1:${uiPort}`;
const pythonPath = [repoRoot, process.env.PYTHONPATH].filter(Boolean).join(path.delimiter);
const pythonExecutable = process.env.BAIOS_E2E_PYTHON || "python";
const runtimeMode = process.env.BAIOS_E2E_RUNTIME_MODE || "development";
const production = runtimeMode === "production";
const projectMatrix = JSON.parse(fs.readFileSync(new URL("./e2e/project-matrix.json", import.meta.url), "utf8"));
if (
  projectMatrix.schema !== "businessaios_browser_project_matrix.v2"
  || !Array.isArray(projectMatrix.projects) || !projectMatrix.projects.length
  || !Array.isArray(projectMatrix.scenarios) || !projectMatrix.scenarios.length
) {
  throw new Error("invalid canonical browser proof contract");
}
const projectNames = projectMatrix.projects.map((entry) => String(entry?.name || "").trim());
if (projectNames.some((name) => !name) || new Set(projectNames).size !== projectNames.length) {
  throw new Error("canonical browser project names must be non-empty and unique");
}
const projects = projectMatrix.projects.map((entry) => {
  const device = devices[entry.device];
  if (!device) throw new Error(`unknown Playwright device in canonical matrix: ${entry.device}`);
  if (!["chromium", "firefox", "webkit"].includes(entry.engine)) throw new Error(`invalid browser engine: ${entry.engine}`);
  if (!["desktop", "mobile"].includes(entry.surface)) throw new Error(`invalid browser surface: ${entry.surface}`);
  return { name: entry.name, use: { ...device, browserName: entry.engine } };
});
const productionRequired = [
  "DATABASE_URL", "DECISION_SIGNING_SECRET", "API_CONTROL_PLANE_API_KEY_PEPPER",
  "BUSINESAIOS_KEY_PROVIDER_MASTER_KEY_B64", "BUSINESAIOS_ENABLE_POSTGRES_EVENT_STORE"
];
const missingProduction = productionRequired.filter((key) => !String(process.env[key] || "").trim());
if (production && missingProduction.length) throw new Error(`production browser runtime missing: ${missingProduction.join(",")}`);

export default defineConfig({
  testDir: "./e2e",
  timeout: 90_000,
  expect: { timeout: 10_000 },
  fullyParallel: false,
  workers: 1,
  retries: 0,
  reporter: [
    ["list"],
    ["junit", { outputFile: path.join(artifacts, "junit.xml") }],
    ["json", { outputFile: path.join(artifacts, "playwright.json") }],
    ["html", { outputFolder: path.join(artifacts, "html"), open: "never" }]
  ],
  outputDir: path.join(artifacts, "test-results"),
  use: {
    baseURL: uiTarget,
    trace: "off",
    screenshot: "only-on-failure",
    video: "retain-on-failure"
  },
  projects,
  webServer: [
    {
      name: production ? "Production API" : "Isolated API",
      command: `"${pythonExecutable}" ../scripts/server/run_profile.py`,
      cwd: path.resolve("."),
      url: `${apiTarget}/health`,
      reuseExistingServer: false,
      timeout: 60_000,
      stdout: "pipe",
      stderr: "pipe",
      env: {
        ...process.env,
        APP_PROFILE: "api",
        APP_ENV: production ? "production" : "dev",
        ENV: production ? "production" : "dev",
        API_HOST: "127.0.0.1",
        API_PORT: apiPort,
        APP_RUNTIME_DATA_DIR: path.join(runtimeRoot, "runtime"),
        BUSINESAIOS_DATA_DIR: path.join(runtimeRoot, "runtime"),
        DATA_DIR: path.join(runtimeRoot, "data"),
        BUSINESAIOS_API_KEY_STORE_BACKEND: production ? "file" : (process.env.BUSINESAIOS_API_KEY_STORE_BACKEND || "file"),
        BUSINESAIOS_API_KEY_STORE_PATH: path.join(runtimeRoot, "api_keys.json"),
        BUSINESAIOS_TENANT_REGISTRY_PATH: path.join(runtimeRoot, "tenant_registry.json"),
        API_CONTROL_PLANE_ALLOW_DEV_FALLBACKS: production ? "0" : (process.env.API_CONTROL_PLANE_ALLOW_DEV_FALLBACKS || "1"),
        API_CONTROL_PLANE_API_KEY_PEPPER: process.env.API_CONTROL_PLANE_API_KEY_PEPPER || "canonical-browser-e2e-pepper",
        BUSINESAIOS_KEY_PROVIDER_BACKEND: production ? "file" : (process.env.BUSINESAIOS_KEY_PROVIDER_BACKEND || "memory"),
        FORWARDED_ALLOW_IPS: "203.0.113.254",
        BUSINESAIOS_TRUST_PROXY_HEADERS: "1",
        BUSINESAIOS_TRUSTED_PROXY_IPS: "127.0.0.1/32",
        PYTHONPATH: pythonPath
      }
    },
    {
      name: "Production frontend preview",
      command: `npm run build && npm run preview -- --host 127.0.0.1 --port ${uiPort}`,
      cwd: path.resolve("."),
      url: uiTarget,
      reuseExistingServer: false,
      timeout: 60_000,
      stdout: "pipe",
      stderr: "pipe",
      env: { ...process.env, VITE_API_BASE: "/api", BAIOS_E2E_API_TARGET: apiTarget }
    }
  ]
});
