import { expect, test } from "@playwright/test";

test("support console rejects owner credentials and processes bounded cases without key persistence", async ({ page }) => {
  const item = {
    id: "0c2d6f9e-558a-42ba-aa3e-99135c3be0aa",
    tenant_id: "tenant-a", business_id: "business-a", category: "technical",
    summary: "Messages are not delivered", created_by_member_id: "owner-a",
    status: "open", claimed_by_operator_user_id: null, revision: 1,
    created_at: "2026-10-09T12:00:00+00:00",
    updated_at: "2026-10-09T12:00:00+00:00",
    claimed_at: null, resolved_at: null
  };
  const observed = [];
  await page.route("**/api/platform-support/**", async (route) => {
    const req = route.request();
    const key = req.headers()["x-api-key"];
    const path = new URL(req.url()).pathname;
    const respond = (status, body) => route.fulfill({ status, contentType: "application/json", body: JSON.stringify(body) });
    if (key !== "scoped-operator-key") {
      return respond(key === "owner-key" ? 403 : 401, { detail: "support_case_operator_scope_required" });
    }
    if (path.endsWith("/session")) {
      return respond(200, {
        tenant_id: "tenant-a", business_id: "business-a", operator_id: "operator-one",
        can_manage_cases: true
      });
    }
    if (path.endsWith("/cases")) return respond(200, { cases: item.status === "resolved" ? [] : [item] });
    if (req.method() === "GET" && path.endsWith("/cases/" + item.id + "/history")) {
      const entries = [{ revision: 1, action: "created", status: "open", occurred_at: item.created_at }];
      if (item.revision >= 2) {
        entries.push({ revision: 2, action: "claimed", status: "claimed", occurred_at: item.updated_at });
      }
      if (item.revision >= 3) {
        entries.push({ revision: 3, action: "resolved", status: "resolved", occurred_at: item.updated_at });
      }
      return respond(200, {
        case_id: item.id, revision: item.revision, total: entries.length,
        truncated: false, entries
      });
    }
    if (req.method() === "GET" && path.endsWith("/cases/" + item.id)) {
      return respond(200, item);
    }
    if (req.method() === "POST" && path.includes("/cases/")) {
      const action = path.split("/").pop();
      const body = req.postDataJSON();
      observed.push({ action, ...body });
      if (body.expected_revision !== item.revision) {
        return respond(409, { detail: "support_case_revision_conflict" });
      }
      if (action === "claim" && item.status === "open") {
        item.status = "claimed";
        item.claimed_by_operator_user_id = "operator-one";
      } else if (action === "resolve" && item.status === "claimed") {
        item.status = "resolved";
      } else {
        return respond(409, { detail: "support_case_not_claimed_by_operator" });
      }
      item.revision += 1;
      return respond(200, item);
    }
    return respond(404, { detail: "not_found" });
  });

  await page.goto("/?support_console=1");
  await expect(page.getByRole("heading", { name: "Очередь обращений" })).toBeVisible();
  await expect(page.getByRole("heading", { name: /Подключите бизнес/ })).toHaveCount(0);
  const secret = page.getByLabel("Ключ доступа оператора");
  await secret.fill("owner-key");
  await page.getByRole("button", { name: "Войти в поддержку" }).click();
  await expect(page.getByRole("alert")).toContainText("Не удалось открыть очередь");
  await expect(page.getByText("Messages are not delivered")).toHaveCount(0);

  await secret.fill("scoped-operator-key");
  await page.getByRole("button", { name: "Войти в поддержку" }).click();
  await expect(page.getByText("Messages are not delivered")).toBeVisible();
  await expect(page.getByText("Бизнес: business-a")).toBeVisible();
  await page.getByRole("button", { name: "Показать историю" }).click();
  await expect(page.getByText("Подтверждено событий: 1")).toBeVisible();
  await expect(page.getByText(/Создано ·/)).toBeVisible();
  await page.getByRole("button", { name: "Скрыть историю" }).click();
  await page.getByRole("button", { name: "Взять в работу" }).click();
  await expect(page.getByRole("button", { name: "Закрыть обращение" })).toBeVisible();
  await page.getByRole("button", { name: "Закрыть обращение" }).click();
  await expect(page.getByText("В очереди нет открытых обращений.")).toBeVisible();
  await expect(page.getByText("Messages are not delivered")).toHaveCount(0);
  const lookup = page.getByLabel("Номер обращения");
  await lookup.fill("not-a-uuid");
  await page.getByRole("button", { name: "Найти историю" }).click();
  await expect(page.getByRole("alert")).toContainText("Введите корректный номер");
  await lookup.fill("00000000-0000-0000-0000-000000000099");
  await page.getByRole("button", { name: "Найти историю" }).click();
  await expect(page.getByRole("alert")).toContainText("Не удалось получить обращение");
  await lookup.fill(item.id);
  await page.getByRole("button", { name: "Найти историю" }).click();
  await expect(page.getByRole("region", { name: "Результат поиска истории" })).toBeVisible();
  await expect(page.getByRole("region", { name: "Результат поиска истории" })).toContainText(item.summary);
  await expect(page.getByRole("region", { name: "Результат поиска истории" })).toContainText("resolved");
  await expect(page.getByText("Подтверждено событий: 3")).toBeVisible();
  await expect(page.getByText(/Взято в работу ·/)).toBeVisible();
  await expect(page.getByText(/Решено ·/)).toBeVisible();
  expect(observed.map((row) => row.action)).toEqual(["claim", "resolve"]);
  expect(observed.map((row) => row.expected_revision)).toEqual([1, 2]);
  expect(observed.every((row) => String(row.idempotency_key).startsWith("support-op-"))).toBe(true);
  const containsSecret = await page.evaluate(() => {
    const text = [...[localStorage, sessionStorage]].flatMap((store) =>
      Array.from({ length: store.length }, (_, i) => store.key(i) + "=" + store.getItem(store.key(i)))
    ).join(" ");
    return text.includes("scoped-operator-key");
  });
  expect(containsSecret).toBe(false);
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth + 1);
  expect(overflow).toBe(false);

  await page.reload();
  await expect(page.getByLabel("Ключ доступа оператора")).toHaveValue("");
  await expect(page.getByText("Messages are not delivered")).toHaveCount(0);
});
