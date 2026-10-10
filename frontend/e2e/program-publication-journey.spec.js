import { expect, test } from "@playwright/test";

function browserId(value) {
  return String(value || "browser").toLowerCase().replace(/[^a-z0-9]+/g, "-");
}

test("owner creates and publishes a multi-lesson program through the canonical catalog", async ({ page }, testInfo) => {
  const suffix = browserId(testInfo.project.name);
  const title = "Обучающая программа " + suffix;
  await page.goto("/");
  await expect(page.getByRole("heading", { name: /Подключите бизнес/ })).toBeVisible();
  await page.getByLabel("Название бизнеса").fill("Programs E2E " + suffix);
  await page.getByLabel("Email владельца").fill("programs-" + suffix + "@example.test");
  await page.getByLabel("Сфера").fill("education");
  await page.getByLabel("Город").fill("Amsterdam");
  await page.getByRole("button", { name: /Продолжить/ }).click();
  await page.getByRole("button", { name: /Больше клиентов/ }).click();
  await page.getByRole("button", { name: /Продолжить/ }).click();
  await page.locator("button.integration-card:not([disabled])").first().click();
  await page.getByRole("button", { name: /Продолжить/ }).click();
  await page.getByRole("button", { name: /Советник/ }).click();

  const registration = page.waitForResponse((response) =>
    response.url().includes("/api/public-site/cta/start") &&
    response.request().method() === "POST");
  await page.getByRole("button", { name: /Создать мой BusinessAIOS/ }).click();
  const result = await registration;
  expect(result.status()).toBe(200);
  const account = await result.json();
  expect(account.owner_session?.api_key).toBeTruthy();

  const panel = page.getByRole("region", { name: "Программы обучения" });
  await expect(panel.getByRole("heading", { name: "Программы обучения" })).toBeVisible();
  await panel.getByLabel("Название программы").fill(title);
  await panel.getByLabel("Название урока").fill("Вводный урок");
  await panel.getByLabel("Ссылка HTTPS или идентификатор сохранённого материала")
    .fill("https://example.org/lesson-one");
  await panel.getByRole("button", { name: "Добавить урок" }).click();
  await panel.getByLabel("Название урока").nth(1).fill("Практическое занятие");
  await panel.getByLabel("Тип материала").nth(1).selectOption("task");
  await panel.getByLabel("Ссылка HTTPS или идентификатор сохранённого материала")
    .nth(1).fill("asset:practice-lesson");
  const apiPath = "/api/business-workspace/programs";
  const before = await page.request.get(apiPath, {
    headers: { "X-API-Key": account.owner_session.api_key },
  });
  expect(before.status()).toBe(200);
  expect((await before.json()).programs).toEqual([]);

  await panel.getByRole("button", { name: "Опубликовать программу" }).click();
  await expect(panel.getByRole("status")).toContainText("Программа сохранена и опубликована");
  await expect(panel.getByText(title)).toBeVisible();
  await expect(panel.getByText("Уроков: 2")).toBeVisible();
  await panel.getByRole("button", { name: "Обновить каталог" }).click();
  await expect(panel.getByText(title)).toBeVisible();
  const receipt = await page.request.get(apiPath, {
    headers: { "X-API-Key": account.owner_session.api_key },
  });
  expect(receipt.status()).toBe(200);
  const programs = (await receipt.json()).programs;
  expect(programs).toHaveLength(1);
  expect(programs[0].title).toBe(title);
  expect(programs[0].status).toBe("active");
  expect(programs[0].lessons.map((item) => item.position)).toEqual([1, 2]);
  expect(programs[0].lessons.map((item) => item.content_kind)).toEqual(["link", "task"]);
  expect(programs[0].tenant_id).toBe(account.tenant_id);
  expect(programs[0].business_id).toBe(account.business_id);
  const overflow = await page.evaluate(() =>
    document.documentElement.scrollWidth > document.documentElement.clientWidth + 1);
  expect(overflow).toBe(false);
  const stored = await page.evaluate(() =>
    [...Object.entries(localStorage), ...Object.entries(sessionStorage)]
      .some(([key, value]) => (key + value).includes("ak_")));
  expect(stored).toBe(false);
});
