import { expect, test } from "@playwright/test";

function browserId(name) {
  return String(name || "browser").toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");
}

test("event landing owner journey: draft stays private, publish becomes public, unpublish revokes access", async ({ page }, testInfo) => {
  const suffix = browserId(testInfo.project.name);
  const eventId = "event-landing-e2e-" + suffix + "-" + Date.now();
  const title = "Подтверждённое мероприятие " + suffix;

  await page.goto("/");
  await expect(page.getByRole("heading", { name: /Подключите бизнес/ })).toBeVisible();

  await page.getByLabel("Название бизнеса").fill("Event landing E2E " + suffix);
  await page.getByLabel("Email владельца").fill("event-landing-" + suffix + "@example.test");
  await page.getByLabel("Сфера").fill("services");
  await page.getByLabel("Город").fill("Amsterdam");
  await page.getByRole("button", { name: /Продолжить/ }).click();
  await page.getByRole("button", { name: /Больше клиентов/ }).click();
  await page.getByRole("button", { name: /Продолжить/ }).click();
  await page.locator("button.integration-card:not([disabled])").first().click();
  await page.getByRole("button", { name: /Продолжить/ }).click();
  await page.getByRole("button", { name: /Советник/ }).click();

  const registration = page.waitForResponse((response) =>
    response.url().includes("/api/public-site/cta/start") && response.request().method() === "POST");
  await page.getByRole("button", { name: /Создать мой BusinessAIOS/ }).click();
  const response = await registration;
  expect(response.status()).toBe(200);
  const account = await response.json();
  expect(account.owner_session?.api_key).toBeTruthy();

  const panel = page.locator(".event-landing-editor");
  await expect(panel.getByRole("heading", { name: "Страница мероприятия" })).toBeVisible();
  await panel.getByLabel("ID мероприятия").fill(eventId);
  await panel.getByLabel("Название мероприятия *").fill(title);
  await panel.getByLabel("Описание").fill("Описание создаётся в черновике владельца.");
  await panel.getByRole("button", { name: "Создать черновик" }).click();
  await expect(panel.getByText(/Черновик создан/)).toBeVisible();
  await expect(panel.getByText(/Статус: черновик/)).toBeVisible();

  const apiPublicUrl = "/api/public-site/events/" +
    encodeURIComponent(account.tenant_id) + "/" +
    encodeURIComponent(account.business_id) + "/" + encodeURIComponent(eventId);
  const unpublished = await page.request.get(apiPublicUrl);
  expect(unpublished.status()).toBe(404);

  await panel.getByRole("button", { name: "Опубликовать" }).click();
  await expect(panel.getByText(/Опубликовано/)).toBeVisible();
  const publicUrl = await panel.locator("a[href*='event_tenant=']").getAttribute("href");
  expect(publicUrl).toContain("event_id=" + encodeURIComponent(eventId));
  const publicPage = await page.context().newPage();
  try {
    await publicPage.goto(publicUrl);
    await expect(publicPage.getByRole("heading", { name: title, level: 1 })).toBeVisible();
    await expect(publicPage.getByText("Описание создаётся в черновике владельца.")).toBeVisible();
    await expect(publicPage.getByRole("heading", { name: "Страница мероприятия" })).toHaveCount(0);
  } finally {
    await publicPage.close();
  }

  await panel.getByRole("button", { name: "Снять с публикации" }).click();
  await expect(panel.getByText(/Снято с публикации/)).toBeVisible();
  const removed = await page.request.get(apiPublicUrl);
  expect(removed.status()).toBe(404);
});
