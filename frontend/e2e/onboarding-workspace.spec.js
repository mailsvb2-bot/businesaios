import { expect, test } from "@playwright/test";

const BUSINESS_NAME = "Canonical Browser E2E Business";

async function persistentBrowserStateContains(page, secret) {
  const webStorageContains = await page.evaluate((needle) => {
    const values = [];
    for (const storage of [localStorage, sessionStorage]) {
      for (let index = 0; index < storage.length; index += 1) {
        const key = storage.key(index);
        values.push(key, storage.getItem(key));
      }
    }
    return values.some((value) => String(value || "").includes(needle));
  }, secret);
  const cookieContains = (await page.context().cookies()).some((cookie) => String(cookie.value || "").includes(secret));
  const indexedDbCreated = await page.evaluate(async () => (await indexedDB.databases()).length > 0);
  return webStorageContains || cookieContains || indexedDbCreated;
}

test("onboarding creates a read-only OWNER workspace without persisting the API key", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { name: /Подключите бизнес/ })).toBeVisible();

  await page.getByLabel("Название бизнеса").fill(BUSINESS_NAME);
  await page.getByLabel("Email владельца").fill("browser-e2e@example.test");
  await page.getByLabel("Сфера").fill("services");
  await page.getByLabel("Город").fill("Amsterdam");
  await page.getByRole("button", { name: /Продолжить/ }).click();

  await page.getByRole("button", { name: /Больше клиентов/ }).click();
  await page.getByRole("button", { name: /Продолжить/ }).click();

  const integration = page.locator("button.integration-card:not([disabled])").first();
  await expect(integration).toBeVisible();
  const providerTitle = (await integration.locator("strong").innerText()).trim();
  await integration.click();
  await expect(page.getByText("Выбрано ✓").first()).toBeVisible();
  await page.getByRole("button", { name: /Продолжить/ }).click();

  await page.getByRole("button", { name: /Советник/ }).click();
  const ctaResponsePromise = page.waitForResponse((response) => response.url().includes("/api/public-site/cta/start") && response.request().method() === "POST");
  const workspaceResponsePromise = page.waitForResponse((response) => response.url().includes("/api/business-workspace/providers") && response.request().method() === "GET");
  await page.getByRole("button", { name: /Создать мой BusinessAIOS/ }).click();

  const ctaResponse = await ctaResponsePromise;
  expect(ctaResponse.status()).toBe(200);
  const cta = await ctaResponse.json();
  const ownerKey = cta?.owner_session?.api_key;
  expect(Boolean(typeof ownerKey === "string" && ownerKey.includes("."))).toBe(true);
  expect(cta.write_actions_enabled).toBe(false);
  expect(cta.approval_required_before_execution).toBe(true);

  const workspaceResponse = await workspaceResponsePromise;
  expect(workspaceResponse.status()).toBe(200);
  const workspace = await workspaceResponse.json();
  expect(workspace.scope_source).toBe("authenticated_owner_session");
  expect(workspace.write_actions_enabled).toBe(false);

  await expect(page.getByRole("heading", { name: BUSINESS_NAME, level: 1 })).toBeVisible();
  await expect(page.getByText("Запись выключена")).toBeVisible();
  await expect(page.getByRole("button", { name: new RegExp(providerTitle) })).toBeVisible();
  await expect(page.getByText("Не удалось открыть защищённый workspace интеграций.")).toHaveCount(0);
  expect(await persistentBrowserStateContains(page, ownerKey)).toBe(false);

  await page.reload();
  await expect(page.getByRole("heading", { name: BUSINESS_NAME, level: 1 })).toBeVisible();
  await expect(page.getByText(/Защищённая OWNER-сессия отсутствует или была потеряна/)).toBeVisible();
  expect(await persistentBrowserStateContains(page, ownerKey)).toBe(false);
});
