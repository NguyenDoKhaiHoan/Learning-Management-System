// Read-only portal smoke check against the running application using database lms.
import { chromium, expect } from "@playwright/test";

const base = process.env.LMS_UI_BASE ?? "http://127.0.0.1:5173";
const browser = await chromium.launch();
try {
  const page = await browser.newPage({
    viewport: { width: 1440, height: 1000 },
  });
  const failures = [];
  page.on("pageerror", (error) => failures.push(error.message));
  page.on("response", (response) => {
    if (response.url().includes("/api/") && response.status() >= 400)
      failures.push(`${response.status()} ${response.url()}`);
  });
  const login = async (actor) => {
    await page.goto(base + "/#/login");
    await page.getByLabel("Email hoặc tên đăng nhập").fill("demo_" + actor);
    await page
      .getByLabel("Mật khẩu", { exact: true })
      .fill(process.env.LMS_DEMO_PASSWORD ?? "LmsDemo-Week2!2026");
    await page.getByRole("button", { name: "Đăng nhập", exact: true }).click();
    await expect(page.getByRole("button", { name: "Đăng xuất" })).toBeVisible();
    await expect(page.locator(".loading")).toHaveCount(0);
  };
  await login("admin");
  await page
    .getByRole("link", { name: "Báo cáo tổng quan", exact: true })
    .click();
  await expect(page.getByRole("table")).toBeVisible();
  await expect(page.getByRole("link", { name: /DEMO_WEEK4/ })).toBeVisible();
  await expect(page.locator(".loading")).toHaveCount(0);
  await page.screenshot({
    path: "../../.local-logs/week5-lms-admin-reports.png",
    fullPage: true,
  });
  await page
    .getByRole("link", { name: "Tài khoản & vai trò", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "demo_student", exact: true }),
  ).toBeVisible();
  await expect(page.locator(".loading")).toHaveCount(0);
  await page.screenshot({
    path: "../../.local-logs/week5-lms-admin-users.png",
    fullPage: true,
  });
  await page.getByRole("button", { name: "Đăng xuất" }).click();
  await login("instructor");
  await expect(
    page.getByRole("heading", { name: "Tổng quan giảng dạy" }),
  ).toBeVisible();
  await page.screenshot({
    path: "../../.local-logs/week5-lms-instructor.png",
    fullPage: true,
  });
  const card = page.getByRole("article").filter({
    has: page.getByRole("heading", {
      name: "Xây dựng ứng dụng với React",
      exact: true,
    }),
  });
  await card
    .getByRole("button", { name: "Quản lý khóa học", exact: true })
    .click();
  await expect(
    page.getByText("Sửa chương", { exact: true }).first(),
  ).toBeVisible();
  await expect(page.locator(".loading")).toHaveCount(0);
  await page.screenshot({
    path: "../../.local-logs/week5-lms-builder.png",
    fullPage: true,
  });
  await page.setViewportSize({ width: 390, height: 844 });
  await expect(page.locator("body")).toHaveJSProperty("scrollWidth", 390);
  await page.screenshot({
    path: "../../.local-logs/week5-lms-builder-mobile.png",
    fullPage: true,
  });
  expect(failures).toEqual([]);
  console.log(
    "Verified lms portals: admin users/reports, instructor dashboard/content builder, desktop/mobile; no API or browser errors.",
  );
} finally {
  await browser.close();
}
