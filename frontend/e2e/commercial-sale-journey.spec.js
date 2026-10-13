import { expect, test } from "@playwright/test";

// Browser contract fixture only. The canonical payment/store HTTP implementation
// is independently covered by Python integration tests; this is NOT live PSP proof.
test("owner can quote, create and recover a canonical sale without inventing payment", async ({ page }, info) => {
  const suffix = info.project.name.toLowerCase().replace(/[^a-z0-9]+/g, "-");
  await page.goto("/");
  await page.getByLabel("Название бизнеса").fill("Commercial E2E " + suffix);
  await page.getByLabel("Email владельца").fill("sales-" + suffix + "@example.test");
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
  const owner = await result.json();
  expect(owner.owner_session?.api_key).toBeTruthy();

  const lead = {
    lead_id: "lead-fixture", customer_id: "customer-fixture", conversation_id: "conversation-fixture",
    channel: "telegram", sales_stage: "new", lifecycle_status: "active"
  };
  const program = {
    id: "paid-fixture", title: "Опубликованная программа", status: "active", access_mode: "paid",
    tenant_id: owner.tenant_id, business_id: owner.business_id, lessons: [
      { position: 1, title: "Урок", content_kind: "text", content_ref: "Материал" }
    ]
  };
  const offer = {
    offer_id: "basic", catalog_id: "catalog-fixture", program_id: program.id,
    amount_minor: 89000, currency: "RUB", fingerprint: "trusted-catalog-fingerprint"
  };
  const created = [];
  const seenKeys = [];
  let failedOrderAttempt = true;
  let unsafeCheckout = true;
  let checkoutAttempts = 0;
  let capturedAuthorization = 0;
  const json = (route, body, status = 200) => route.fulfill({
    status, contentType: "application/json", body: JSON.stringify(body)
  });

  await page.route("**/api/business-workspace/programs", (route) => {
    if (route.request().method() !== "GET") return route.continue();
    return json(route, { programs: [program] });
  });
  await page.route("**/api/business-workspace/commercial/**", async (route) => {
    const req = route.request();
    if (req.headers()["x-api-key"] === owner.owner_session.api_key) capturedAuthorization++;
    const path = new URL(req.url()).pathname;
    if (path.endsWith("/leads") && req.method() === "GET")
      return json(route, { leads: [lead] });
    if (path.endsWith("/offers/" + program.id) && req.method() === "GET")
      return json(route, { program_id: program.id, offers: [offer] });
    if (path.endsWith("/orders") && req.method() === "GET")
      return json(route, { orders: created });
    if (path.endsWith("/orders") && req.method() === "POST") {
      const body = req.postDataJSON();
      seenKeys.push(body.idempotency_key);
      expect(Object.keys(body).sort()).toEqual(
        ["customer_id", "idempotency_key", "lead_id", "offer_id", "program_id"].sort());
      expect(body.lead_id).toBe(lead.lead_id);
      expect(body.customer_id).toBe(lead.customer_id);
      expect(body.program_id).toBe(program.id);
      expect(body.offer_id).toBe(offer.offer_id);
      if (failedOrderAttempt) {
        failedOrderAttempt = false;
        return json(route, { detail: "temporary_failure" }, 503);
      }
      const order = {
        order_id: "order-fixture", invoice_id: "invoice-fixture",
        customer_id: lead.customer_id, lead_id: lead.lead_id,
        program_id: program.id, offer_id: offer.offer_id,
        currency: offer.currency, amount_minor: offer.amount_minor,
        paid_minor: 0, invoice_status: "issued",
        status: "active", provider_verified: false
      };
      if (!created.length) created.push(order);
      return json(route, order);
    }
    if (path.endsWith("/orders/order-fixture") && req.method() === "GET")
      return json(route, created[0]);
    if (path.endsWith("/orders/order-fixture/checkout") && req.method() === "POST") {
      checkoutAttempts++;
      return json(route, {
        ...created[0], tenant_id: owner.tenant_id, business_id: owner.business_id,
        status: "awaiting_payment", external_reference: "psp-fixture",
        checkout_url: unsafeCheckout ? "http://unsafe.example/pay" : "https://payments.example.test/pay"
      });
    }
    return json(route, { detail: "fixture_unhandled_route" }, 404);
  });
  const panel = page.getByRole("region", { name: "Заказы и платежи" });
  await panel.getByRole("button", { name: "Обновить" }).click();
  const submit = panel.getByRole("button", { name: "Создать заказ и счёт" });
  await expect(submit).toBeDisabled();
  await panel.getByLabel("Обращение клиента").selectOption(lead.lead_id);
  await panel.getByLabel("Опубликованная платная программа").selectOption(program.id);
  await expect(panel.getByLabel("Предложение с проверенной серверной ценой"))
    .toContainText("890");
  await panel.getByLabel("Предложение с проверенной серверной ценой")
    .selectOption(offer.offer_id);
  await expect(submit).toBeEnabled();
  await submit.click();
  await expect(panel.getByRole("alert")).toContainText("Создание счёта не завершено");
  expect(created).toHaveLength(0);
  await submit.click();
  await expect(panel.getByRole("status")).toContainText("Заказ и счёт сохранены");
  expect(seenKeys).toHaveLength(2);
  expect(seenKeys[0]).toBe(seenKeys[1]);
  expect(created).toHaveLength(1);
  await expect(panel.getByText("Счёт выставлен, оплата не подтверждена")).toBeVisible();
  await panel.getByRole("button", { name: "Получить ссылку PSP" }).click();
  await expect(panel.getByRole("alert")).toContainText("Checkout недоступен");
  await expect(panel.getByRole("link", { name: "Перейти к защищённой оплате" })).toHaveCount(0);
  unsafeCheckout = false;
  await panel.getByRole("button", { name: "Получить ссылку PSP" }).click();
  const paymentLink = panel.getByRole("link", { name: "Перейти к защищённой оплате" });
  await expect(paymentLink).toHaveAttribute("href", "https://payments.example.test/pay");
  await expect(paymentLink).toHaveAttribute("rel", "noopener noreferrer");
  await expect(panel.getByText(/Пока сервер не подтвердил PSP и исполнение/)).toBeVisible();
  await panel.getByRole("button", { name: "Обновить" }).click();
  await expect(panel.getByText("Счёт выставлен, оплата не подтверждена")).toBeVisible();
  expect(checkoutAttempts).toBe(2);
  expect(capturedAuthorization).toBeGreaterThan(0);
  const leaked = await page.evaluate(() =>
    [...Object.entries(localStorage), ...Object.entries(sessionStorage)]
      .some(([key, value]) => (key + value).includes("ak_")));
  expect(leaked).toBe(false);
});
