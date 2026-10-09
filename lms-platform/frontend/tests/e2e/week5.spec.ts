import { test, expect, type Page } from "@playwright/test";

const password = process.env.LMS_DEMO_PASSWORD ?? "LmsDemo-Week2!2026";
async function login(page: Page, actor: string) {
  await page.goto("/#/login");
  await page.getByLabel("Email hoặc tên đăng nhập").fill("demo_" + actor);
  await page.getByLabel("Mật khẩu", { exact: true }).fill(password);
  await page.getByRole("button", { name: "Đăng nhập", exact: true }).click();
  await expect(page.getByRole("button", { name: "Đăng xuất" })).toBeVisible();
}

test("admin creates and edits accounts, roles, status, searchable pages and reports", async ({
  page,
}) => {
  await login(page, "admin");
  await page
    .getByRole("link", { name: "Tài khoản & vai trò", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "Tài khoản & vai trò" }),
  ).toBeVisible();
  const username = "portal_" + Date.now();
  await page.getByText("+ Tạo tài khoản", { exact: true }).click();
  await page
    .getByLabel("Email mới", { exact: true })
    .fill(username + "@example.test");
  await page.getByLabel("Tên đăng nhập mới", { exact: true }).fill(username);
  await page.getByLabel("Mật khẩu ban đầu").fill(password);
  await page
    .getByRole("button", { name: "Tạo tài khoản", exact: true })
    .click();
  await expect(
    page.getByText("Đã tạo tài khoản.", { exact: true }),
  ).toBeVisible();
  await page.getByLabel("Tìm tài khoản", { exact: true }).fill(username);
  await page.getByRole("button", { name: "Lọc tài khoản" }).click();
  let card = page.locator(".user-card").filter({
    has: page.getByRole("heading", { name: username, exact: true }),
  });
  await expect(card).toBeVisible();
  await expect(
    page.getByRole("link", { name: "Tài khoản & vai trò", exact: true }),
  ).toHaveAttribute("aria-current", "page");
  await card.getByText("Sửa thông tin", { exact: true }).click();
  await card
    .getByLabel("Email", { exact: true })
    .fill(username + "@edited.test");
  await card
    .getByRole("button", { name: "Lưu tài khoản", exact: true })
    .click();
  await expect(card).toContainText(username + "@edited.test");
  await card
    .getByRole("button", { name: "Gán Giảng viên", exact: true })
    .click();
  await expect(
    card.getByRole("button", { name: "Gỡ Giảng viên", exact: true }),
  ).toBeVisible();
  await card.getByRole("button", { name: "Gỡ Học viên", exact: true }).click();
  await expect(
    card.getByRole("button", { name: "Gán Học viên", exact: true }),
  ).toBeVisible();
  await card
    .getByLabel("Trạng thái mới", { exact: true })
    .selectOption("LOCKED");
  await card
    .getByRole("button", { name: "Lưu trạng thái", exact: true })
    .click();
  await expect(card).toContainText("Đã khóa");
  await expect(page.locator(".loading")).toHaveCount(0);
  await page.screenshot({
    path: "test-results/week5-admin-users.png",
    fullPage: true,
  });
  await page
    .getByRole("link", { name: "Báo cáo tổng quan", exact: true })
    .click();
  await expect(page.getByRole("table")).toBeVisible();
  await expect(
    page.getByRole("columnheader", { name: "Ghi danh", exact: true }),
  ).toBeVisible();
  await page.screenshot({
    path: "test-results/week5-admin-reports.png",
    fullPage: true,
  });
  await page.setViewportSize({ width: 390, height: 844 });
  await expect(page.locator("body")).toHaveJSProperty("scrollWidth", 390);
  await page.screenshot({
    path: "test-results/week5-reports-mobile.png",
    fullPage: true,
  });
  await page
    .getByRole("link", { name: "Tài khoản & vai trò", exact: true })
    .click();
  await page
    .getByLabel("Tìm tài khoản", { exact: true })
    .fill("missing-unique-account");
  await page.getByRole("button", { name: "Lọc tài khoản" }).click();
  await expect(page.getByText("Không có tài khoản phù hợp.")).toBeVisible();
});

test("instructor builds, edits, reorders, attaches resources, publishes and deletes draft content", async ({
  page,
}) => {
  await login(page, "instructor");
  await expect(
    page.getByRole("heading", { name: "Tổng quan giảng dạy" }),
  ).toBeVisible();
  await page.screenshot({
    path: "test-results/week5-instructor.png",
    fullPage: true,
  });
  const title = "Builder " + Date.now();
  await page.getByText("+ Tạo khóa học mới", { exact: true }).click();
  await page
    .getByLabel("Mã khóa học", { exact: true })
    .fill("BUILD_" + Date.now());
  await page.getByLabel("Tên khóa học", { exact: true }).fill(title);
  await page.getByRole("button", { name: "Tạo khóa học", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: title, exact: true }),
  ).toBeVisible();
  await page.getByText("Thông tin & quản lý khóa học", { exact: true }).click();
  await page.getByLabel("Tên khóa học chỉnh sửa").fill(title + " edited");
  await page.getByRole("button", { name: "Lưu thông tin khóa học" }).click();
  await expect(
    page.getByRole("heading", { name: title + " edited", exact: true }),
  ).toBeVisible();
  await page.getByLabel("Tên chương mới").fill("First module");
  await page.getByRole("button", { name: "Thêm chương", exact: true }).click();
  for (const title of ["First lesson", "Second lesson"]) {
    await page.getByText("+ Thêm bài học", { exact: true }).click();
    await page.getByLabel("Tên bài học", { exact: true }).fill(title);
    await page
      .getByLabel("Nội dung bài học", { exact: true })
      .fill("Content " + title);
    await page
      .getByRole("button", { name: "Lưu bài học", exact: true })
      .click();
    await expect(page.getByText(title, { exact: true })).toBeVisible();
  }
  await page.getByText("Sửa chương", { exact: true }).click();
  await page.getByLabel("Tên chương chỉnh sửa").fill("Renamed module");
  await page.getByRole("button", { name: "Lưu chương", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: /Renamed module/ }),
  ).toBeVisible();
  let second = page.locator("details.lesson").filter({
    has: page.locator("summary").filter({ hasText: /^Second lesson$/ }),
  });
  await second.locator(":scope > summary").click();
  await second.getByText("Sửa bài học", { exact: true }).click();
  await second.getByLabel("Nội dung chỉnh sửa").fill("Revised lesson content");
  await second
    .getByRole("button", { name: "Lưu nội dung bài học", exact: true })
    .click();
  await second.locator(":scope > summary").click();
  await expect(second.locator(".lesson-text")).toBeVisible();
  await second.getByText("Sửa bài học", { exact: true }).click();
  await second.getByRole("button", { name: "Đưa lên", exact: true }).click();
  await expect(page.locator("details.lesson > summary").first()).toHaveText(
    "Second lesson",
  );
  await second.locator(":scope > summary").click();
  await second
    .getByLabel("Tên liên kết", { exact: true })
    .fill("Tài liệu tham khảo");
  await second
    .getByLabel("URL", { exact: true })
    .fill("https://example.com/reference");
  await second
    .getByRole("button", { name: "Thêm liên kết", exact: true })
    .click();
  await second.locator(":scope > summary").click();
  await expect(
    second.getByText("Tài liệu tham khảo", { exact: true }),
  ).toBeVisible();
  await second.getByLabel("Tệp bài học").setInputFiles({
    name: "lesson.pdf",
    mimeType: "application/pdf",
    buffer: Buffer.from("%PDF-1.7\nlesson resource"),
  });
  await second.getByRole("button", { name: "Upload tệp", exact: true }).click();
  await second.locator(":scope > summary").click();
  await expect(second.getByText("lesson.pdf", { exact: true })).toBeVisible();
  await page
    .getByLabel("Yêu cầu điểm bài thi đã công bố", { exact: true })
    .check();
  await page.getByLabel("Ngưỡng điểm đạt (%)", { exact: true }).fill("75.5");
  await page.getByRole("button", { name: "Lưu điều kiện hoàn thành" }).click();
  await expect(
    page.getByLabel("Yêu cầu điểm bài thi đã công bố", { exact: true }),
  ).toBeChecked();
  await page.screenshot({
    path: "test-results/week5-builder.png",
    fullPage: true,
  });
  await page
    .getByRole("button", { name: "Công bố khóa học", exact: true })
    .click();
  await expect(
    page.getByRole("button", { name: "Chuyển về bản nháp", exact: true }),
  ).toBeVisible();
  await expect(page.getByLabel("Tên chương chỉnh sửa")).toHaveCount(0);
  await page
    .getByRole("button", { name: "Chuyển về bản nháp", exact: true })
    .click();
  let first = page.locator("details.lesson").filter({
    has: page.locator("summary").filter({ hasText: /^First lesson$/ }),
  });
  await first.locator(":scope > summary").click();
  await first.getByText("Sửa bài học", { exact: true }).click();
  await first.getByText("Xóa bài học", { exact: true }).click();
  await first
    .getByRole("button", { name: "Xác nhận xóa bài học", exact: true })
    .click();
  await expect(page.getByText("First lesson", { exact: true })).toHaveCount(0);
  await page.getByText("Thông tin & quản lý khóa học", { exact: true }).click();
  await page.getByText("Xóa khóa học", { exact: true }).click();
  await page
    .getByRole("button", { name: "Xác nhận xóa khóa học", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "Tổng quan giảng dạy" }),
  ).toBeVisible();
});

test("nested role guards stop forbidden API calls and unknown routes show a page", async ({
  page,
}) => {
  await login(page, "student");
  let adminCalls = 0;
  page.on("request", (request) => {
    if (/\/api\/v1\/(users|reports)/.test(request.url())) adminCalls++;
  });
  for (const path of [
    "/admin/users?offset=10",
    "/admin/reports",
    "/instructor",
  ]) {
    await page.goto("/#" + path);
    await expect(
      page.getByRole("heading", { name: "Không có quyền truy cập" }),
    ).toBeVisible();
  }
  expect(adminCalls).toBe(0);
  await page.goto("/#/unknown");
  await expect(
    page.getByText("Trang không tồn tại.", { exact: true }),
  ).toBeVisible();
});

test("loading, server errors, retry and stale responses preserve the active page", async ({
  page,
}) => {
  await login(page, "admin");
  await page.route("**/api/v1/reports/overview?**", (route) =>
    route.fulfill({
      status: 503,
      contentType: "application/json",
      body: JSON.stringify({
        code: "UNAVAILABLE",
        message: "Unavailable",
        details: [],
        trace_id: "test-retry",
      }),
    }),
  );
  await page
    .getByRole("link", { name: "Báo cáo tổng quan", exact: true })
    .click();
  await expect(
    page.getByRole("button", { name: "Thử tải lại", exact: true }),
  ).toBeVisible();
  await expect(page.locator("#messages")).toContainText("test-retry");
  await page.unroute("**/api/v1/reports/overview?**");
  await page.getByRole("button", { name: "Thử tải lại", exact: true }).click();
  await expect(page.getByRole("table")).toBeVisible();
  let release!: () => void;
  const pending = new Promise<void>((resolve) => {
    release = resolve;
  });
  await page.route("**/api/v1/users?**", async (route) => {
    await pending;
    await route.continue();
  });
  await page
    .getByRole("link", { name: "Tài khoản & vai trò", exact: true })
    .click();
  await expect(page.locator(".loading")).toHaveText("Đang tải…");
  await page
    .getByRole("link", { name: "Báo cáo tổng quan", exact: true })
    .click();
  await expect(page.getByRole("table")).toBeVisible();
  release();
  await expect(
    page.getByRole("heading", { name: "Báo cáo tổng quan", exact: true }),
  ).toBeVisible();
  await expect(page.locator(".user-card")).toHaveCount(0);
});

test("three portals remain usable on mobile and expose labelled controls", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  for (const [actor, path, heading] of [
    ["admin", "/admin", "Khóa học của bạn"],
    ["instructor", "/instructor", "Tổng quan giảng dạy"],
    ["student", "/student", "Hôm nay, bạn muốn học gì?"],
  ] as const) {
    await login(page, actor);
    await page.goto("#" + path);
    await expect(page.getByRole("heading", { name: heading, exact: true })).toBeVisible();
    await expect(page.locator("nav[aria-label='Điều hướng chính']")).toBeVisible();
    await expect(page.locator("body")).toHaveJSProperty("scrollWidth", 390);
    const unlabeled = await page.locator("input, textarea, select, button").evaluateAll((controls) =>
      controls.filter((control) => {
        const label = control.getAttribute("aria-label") || control.textContent ||
          (control.id && document.querySelector(`label[for='${control.id}']`)?.textContent);
        return !label?.trim();
      }).length,
    );
    expect(unlabeled).toBe(0);
    await page.getByRole("button", { name: "Đăng xuất" }).click();
  }
});
