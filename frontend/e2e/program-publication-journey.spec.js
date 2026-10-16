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
  // The owner can safely leave a draft and resume it without retyping lessons.
  const draftTitle = "Черновик программы " + suffix;
  await panel.getByLabel("Название программы").fill(draftTitle);
  await panel.getByRole("button", { name: "Сохранить черновик" }).click();
  await expect(panel.getByText(/Черновик сохранён в BusinessAIOS/)).toBeVisible();
  await panel.getByRole("button", { name: "Новая программа" }).click();
  await expect(panel.getByText(draftTitle)).toBeVisible();
  await panel.getByRole("button", { name: "Обновить каталог" }).click();
  await panel.getByRole("button", { name: "Продолжить черновик" }).click();
  await expect(panel.getByLabel("Название программы")).toHaveValue(draftTitle);
  await panel.getByLabel("Название урока").fill("Первый сохранённый урок");
  await panel.getByLabel("Ссылка HTTPS или идентификатор сохранённого материала")
    .fill("https://example.org/saved-lesson");
  await panel.getByRole("button", { name: "Сохранить черновик" }).click();
  await expect(panel.getByText(/Черновик сохранён в BusinessAIOS/)).toBeVisible();
  await panel.getByRole("button", { name: "Опубликовать черновик" }).click();
  await expect(panel.getByText(/Программа сохранена и опубликована/)).toBeVisible();
  const finalReceipt = await page.request.get(apiPath, {
    headers: { "X-API-Key": account.owner_session.api_key },
  });
  expect(finalReceipt.status()).toBe(200);
  const finalPrograms = (await finalReceipt.json()).programs;
  expect(finalPrograms).toHaveLength(2);
  const newProgram = finalPrograms.find((item) => item.title === draftTitle);
  expect(newProgram?.status).toBe("active");
  expect(newProgram?.lessons.map((item) => item.title)).toEqual(["Первый сохранённый урок"]);
  const draftReceipt = await page.request.get("/api/business-workspace/program-drafts", {
    headers: { "X-API-Key": account.owner_session.api_key },
  });
  expect(draftReceipt.status()).toBe(200);
  expect((await draftReceipt.json()).drafts).toEqual([]);

  // The enrollment UI must use the canonical customer list, never require a
  // manually copied UUID or synthesize a customer when the business has none.
  await expect(panel.getByLabel("Выберите существующего клиента")).toHaveCount(2);
  await expect(panel.getByText("Активных клиентов пока нет", { exact: false })).toHaveCount(2);
  await expect(panel.getByRole("button", { name: "Зачислить без отправки материалов" })).toHaveCount(2);
  for (const enrollButton of await panel.getByRole("button", { name: "Зачислить без отправки материалов" }).all()) {
    await expect(enrollButton).toBeDisabled();
  }
  const enrollmentMissingCustomer = await page.request.post(
    apiPath + "/" + encodeURIComponent(newProgram.id) + "/enrollments",
    { headers: { "X-API-Key": account.owner_session.api_key },
      data: { customer_id: "00000000-0000-4000-8000-000000000001" } },
  );
  expect(enrollmentMissingCustomer.status()).toBe(404);


  // Archiving the currently opened draft must close its editor after the
  // durable server receipt, rather than leave an archived draft editable.
  const archivedTitle = "Архивируемый черновик " + suffix;
  await panel.getByLabel("Название программы").fill(archivedTitle);
  await panel.getByRole("button", { name: "Сохранить черновик" }).click();
  await expect(panel.getByRole("button", { name: "Опубликовать черновик" })).toBeVisible();
  await panel.getByRole("button", { name: "Архивировать черновик" }).click();
  await expect(panel.getByText("Черновик архивирован. Опубликованные программы не затронуты.")).toBeVisible();
  await expect(panel.getByLabel("Название программы")).toHaveValue("");
  await expect(panel.getByRole("button", { name: "Опубликовать программу" })).toBeVisible();
  await expect(panel.getByRole("button", { name: "Продолжить черновик" })).toHaveCount(0);
  const archivedDrafts = await page.request.get("/api/business-workspace/program-drafts", {
    headers: { "X-API-Key": account.owner_session.api_key },
  });
  expect(archivedDrafts.status()).toBe(200);
  expect((await archivedDrafts.json()).drafts).toEqual([]);

  const overflow = await page.evaluate(() =>
    document.documentElement.scrollWidth > document.documentElement.clientWidth + 1);
  expect(overflow).toBe(false);
  const stored = await page.evaluate(() =>
    [...Object.entries(localStorage), ...Object.entries(sessionStorage)]
      .some(([key, value]) => (key + value).includes("ak_")));
  expect(stored).toBe(false);
});
