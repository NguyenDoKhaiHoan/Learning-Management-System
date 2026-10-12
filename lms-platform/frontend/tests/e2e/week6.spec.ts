import { test, expect, type Page } from "@playwright/test";

const password = process.env.LMS_DEMO_PASSWORD ?? "LmsDemo-Week2!2026";
async function login(page: Page, actor: string) {
  await page.goto("/#/login");
  await page.getByLabel("Email hoặc tên đăng nhập").fill("demo_" + actor);
  await page.getByLabel("Mật khẩu", { exact: true }).fill(password);
  await page.getByRole("button", { name: "Đăng nhập", exact: true }).click();
  await expect(page.getByRole("button", { name: "Đăng xuất" })).toBeVisible();
}

test("Admin can filter audit records and Student route guard prevents audit requests", async ({ page }) => {
  await login(page, "admin");
  await page.getByRole("link", { name: "Tài khoản & vai trò", exact: true }).click();
  const username = "audit_" + Date.now();
  await page.getByText("+ Tạo tài khoản", { exact: true }).click();
  await page.getByLabel("Email mới", { exact: true }).fill(username + "@example.test");
  await page.getByLabel("Tên đăng nhập mới", { exact: true }).fill(username);
  await page.getByLabel("Mật khẩu ban đầu").fill(password);
  await page.getByRole("button", { name: "Tạo tài khoản", exact: true }).click();
  await expect(page.getByText("Đã tạo tài khoản.", { exact: true })).toBeVisible();
  await page.getByRole("link", { name: "Nhật ký kiểm toán", exact: true }).click();
  await page.getByLabel("Hành động", { exact: true }).fill("account.create");
  await page.getByRole("button", { name: "Lọc nhật ký" }).click();
  await expect(page.getByRole("heading", { name: "account.create", exact: true }).first()).toBeVisible();
  await page.getByLabel("Hành động", { exact: true }).fill("no.such.action");
  await page.getByRole("button", { name: "Lọc nhật ký" }).click();
  await expect(page.getByText("Không có nhật ký phù hợp.")).toBeVisible();
  await page.getByRole("button", { name: "Đăng xuất" }).click();
  await login(page, "student");
  const requested: string[] = [];
  page.on("request", (request) => { if (request.url().includes("/audit/")) requested.push(request.url()); });
  await page.goto("/#/admin/audit?trace_id=private");
  await expect(page.getByRole("heading", { name: "Không có quyền truy cập" })).toBeVisible();
  expect(requested).toEqual([]);
});
