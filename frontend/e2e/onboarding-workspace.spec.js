import { expect, test } from "@playwright/test";
import fs from "node:fs";

const proofContract = JSON.parse(fs.readFileSync(new URL("./project-matrix.json", import.meta.url), "utf8"));
const canonicalScenario = proofContract.scenarios?.find((item) => item?.id === "onboarding_owner_workspace");
if (!canonicalScenario?.title || canonicalScenario.file !== "onboarding-workspace.spec.js") {
  throw new Error("invalid canonical onboarding browser scenario contract");
}

function projectIdentity(projectName) {
  const slug = String(projectName || "browser").toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");
  return {
    businessName: `Canonical Browser E2E ${projectName}`,
    email: `browser-e2e+${slug}@example.test`
  };
}

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

async function hasNoHorizontalOverflow(page) {
  return page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth + 1);
}

test(canonicalScenario.title, async ({ page }, testInfo) => {
  const { businessName, email } = projectIdentity(testInfo.project.name);
  await page.goto("/");
  await expect(page.getByRole("heading", { name: /Подключите бизнес/ })).toBeVisible();
  expect(await hasNoHorizontalOverflow(page)).toBe(true);

  await page.getByLabel("Название бизнеса").fill(businessName);
  await page.getByLabel("Email владельца").fill(email);
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

  await expect(page.getByRole("heading", { name: businessName, level: 1 })).toBeVisible();
  await expect(page.getByText("Только чтение")).toBeVisible();
  await expect(page.getByRole("button", { name: new RegExp(providerTitle) })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Первый полезный результат" })).toBeVisible();
  const roadmapCapability = workspace.capabilities.find((item) => item.id === "acquisition.whatsapp_reactivation");
  expect(roadmapCapability?.connectable).toBe(false);
  await page.locator("details.capability-roadmap").evaluate((node) => { node.open = true; });
  const roadmapCard = page.locator("article.capability-card", { hasText: "WhatsApp-реактивация" });
  await expect(roadmapCard).toBeVisible();
  await expect(roadmapCard.getByRole("button")).toHaveCount(0);
  await expect(page.getByText("Не удалось открыть защищённый workspace интеграций.")).toHaveCount(0);
  expect(await hasNoHorizontalOverflow(page)).toBe(true);
  expect(await persistentBrowserStateContains(page, ownerKey)).toBe(false);

  const cookiesAfterCreate = await page.context().cookies();
  const resumeCookie = cookiesAfterCreate.find((cookie) => cookie.name === "businessaios_owner_resume");
  const accountCookie = cookiesAfterCreate.find((cookie) => cookie.name === "businessaios_owner_account");
  expect(Boolean(resumeCookie?.httpOnly)).toBe(true);
  expect(Boolean(accountCookie?.httpOnly)).toBe(true);
  expect(String(resumeCookie?.value || "")).not.toBe(ownerKey);
  expect(String(accountCookie?.value || "")).not.toBe(ownerKey);

  const resumedStatusPromise = page.waitForResponse((response) => response.url().includes(`/api/public-site/cta/${cta.intake_id}`) && response.request().method() === "GET");
  const resumedWorkspacePromise = page.waitForResponse((response) => response.url().includes("/api/business-workspace/providers") && response.request().method() === "GET");
  await page.reload();

  const resumedStatusResponse = await resumedStatusPromise;
  expect(resumedStatusResponse.status()).toBe(200);
  const resumedStatus = await resumedStatusResponse.json();
  const resumedOwnerKey = resumedStatus?.owner_session?.api_key;
  expect(Boolean(typeof resumedOwnerKey === "string" && resumedOwnerKey.includes("."))).toBe(true);
  expect(resumedOwnerKey).not.toBe(ownerKey);

  const resumedWorkspaceResponse = await resumedWorkspacePromise;
  expect(resumedWorkspaceResponse.status()).toBe(200);
  const resumedWorkspace = await resumedWorkspaceResponse.json();
  expect(resumedWorkspace.scope_source).toBe("authenticated_owner_session");
  expect(resumedWorkspace.write_actions_enabled).toBe(false);

  await expect(page.getByRole("heading", { name: businessName, level: 1 })).toBeVisible();
  await expect(page.getByText(/Не удалось восстановить защищённый вход/)).toHaveCount(0);
  await expect(page.getByRole("button", { name: new RegExp(providerTitle) })).toBeVisible();
  expect(await hasNoHorizontalOverflow(page)).toBe(true);
  expect(await persistentBrowserStateContains(page, ownerKey)).toBe(false);
  expect(await persistentBrowserStateContains(page, resumedOwnerKey)).toBe(false);

  await page.getByRole("button", { name: "Добавить бизнес" }).click();
  await expect(page.getByRole("heading", { name: /Подключите бизнес/ })).toBeVisible();
  const secondBusinessName = `${businessName} · Second`;
  await page.getByLabel("Название бизнеса").fill(secondBusinessName);
  await page.getByLabel("Email владельца").fill(email);
  await page.getByLabel("Сфера").fill("commerce");
  await page.getByLabel("Город").fill("Tallinn");
  await page.getByRole("button", { name: /Продолжить/ }).click();
  await page.getByRole("button", { name: /Сильнее продажи/ }).click();
  await page.getByRole("button", { name: /Продолжить/ }).click();
  const secondIntegration = page.locator("button.integration-card:not([disabled])").first();
  await secondIntegration.click();
  await page.getByRole("button", { name: /Продолжить/ }).click();
  await page.getByRole("button", { name: /Советник/ }).click();
  const secondCtaPromise = page.waitForResponse((response) => response.url().includes("/api/public-site/cta/start") && response.request().method() === "POST");
  await page.getByRole("button", { name: /Создать мой BusinessAIOS/ }).click();
  const secondCtaResponse = await secondCtaPromise;
  expect(secondCtaResponse.status()).toBe(200);
  const secondCta = await secondCtaResponse.json();
  expect(secondCta.user_id).toBe(cta.user_id);
  expect(secondCta.tenant_id).not.toBe(cta.tenant_id);
  expect(secondCta.business_id).not.toBe(cta.business_id);
  expect(secondCta.owner_businesses).toHaveLength(2);

  const switcher = page.getByRole("combobox", { name: "Выбор бизнеса", exact: true });
  await expect(switcher).toBeVisible();
  await expect(switcher.locator("option")).toHaveCount(2);
  const switchStatusPromise = page.waitForResponse((response) => response.url().includes(`/api/public-site/cta/${cta.intake_id}`) && response.request().method() === "GET");
  await switcher.selectOption(cta.intake_id);
  expect((await switchStatusPromise).status()).toBe(200);
  await expect(page.getByRole("heading", { name: businessName, level: 1 })).toBeVisible();

  await page.goto("/");
  await expect(page.getByRole("heading", { name: "Мои бизнесы" })).toBeVisible();
  await expect(page.getByRole("button", { name: `Открыть бизнес ${businessName}`, exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: `Открыть бизнес ${secondBusinessName}`, exact: true })).toBeVisible();
  expect(await hasNoHorizontalOverflow(page)).toBe(true);
});
