import { defineConfig, devices } from "@playwright/test";
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
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
  webServer: [
    {
      name: "Production API",
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
        APP_ENV: "dev",
        ENV: "dev",
        API_HOST: "127.0.0.1",
        API_PORT: apiPort,
        APP_RUNTIME_DATA_DIR: path.join(runtimeRoot, "runtime"),
        BUSINESAIOS_DATA_DIR: path.join(runtimeRoot, "runtime"),
        DATA_DIR: path.join(runtimeRoot, "data"),
        BUSINESAIOS_API_KEY_STORE_PATH: path.join(runtimeRoot, "api_keys.json"),
        BUSINESAIOS_TENANT_REGISTRY_PATH: path.join(runtimeRoot, "tenant_registry.json"),
        API_CONTROL_PLANE_API_KEY_PEPPER: "canonical-browser-e2e-pepper",
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
