import { test, expect, type Page } from "@playwright/test";

const password = process.env.LMS_DEMO_PASSWORD ?? "LmsDemo-Week2!2026";
async function login(page: Page, name: string) {
  await page.goto("/#/login");
  await page.getByLabel("Email hoặc tên đăng nhập").fill("demo_" + name);
  await page.getByLabel("Mật khẩu", { exact: true }).fill(password);
  await page.getByRole("button", { name: "Đăng nhập", exact: true }).click();
  await expect(page.getByRole("button", { name: "Đăng xuất" })).toBeVisible();
}
async function logout(page: Page) {
  await page.getByRole("button", { name: "Đăng xuất" }).click();
  await expect(
    page.getByRole("heading", { name: "Đăng nhập", exact: true }),
  ).toBeVisible();
}

test("instructor publishes, student requests, instructor approves/suspends, student access follows state", async ({
  page,
}) => {
  const name = "Lớp thực hành " + Date.now();
  await login(page, "instructor");
  await page.getByText("+ Tạo khóa học mới", { exact: true }).click();
  await page
    .getByLabel("Mã khóa học", { exact: true })
    .fill("E2E_" + Date.now());
  await page.getByLabel("Tên khóa học", { exact: true }).fill(name);
  await page.getByRole("button", { name: "Tạo khóa học", exact: true }).click();
  await expect(page.getByRole("heading", { name, exact: true })).toBeVisible();
  const courseUrl = page.url();
  await page.getByLabel("Tên chương mới").fill("Chương đầu tiên");
  await page.getByRole("button", { name: "Thêm chương", exact: true }).click();
  await page.getByText("+ Thêm bài học", { exact: true }).click();
  await page.getByLabel("Tên bài học", { exact: true }).fill("Bài học E2E");
  await page
    .getByLabel("Nội dung bài học", { exact: true })
    .fill("Nội dung chỉ dành cho học viên ACTIVE.");
  await page.getByRole("button", { name: "Lưu bài học", exact: true }).click();
  await expect(page.getByText("Bài học E2E", { exact: true })).toBeVisible();
  await page
    .getByRole("button", { name: "Công bố khóa học", exact: true })
    .click();
  await expect(
    page.getByRole("button", { name: "Chuyển về bản nháp" }),
  ).toBeVisible();
  await logout(page);
  await login(page, "student");
  const card = page
    .getByRole("article")
    .filter({ has: page.getByRole("heading", { name, exact: true }) });
  await card.getByRole("button", { name: "Gửi yêu cầu ghi danh" }).click();
  await expect(
    page.getByText("Đã gửi yêu cầu. Hãy chờ giảng viên duyệt."),
  ).toBeVisible();
  await page.goto(courseUrl);
  await expect(
    page.getByText("Bạn chưa có quyền thực hiện thao tác này.", {
      exact: false,
    }),
  ).toBeVisible();
  await logout(page);
  await login(page, "instructor");
  await page.goto(courseUrl);
  await page.getByRole("button", { name: "Kích hoạt", exact: true }).click();
  await expect(
    page.getByRole("button", { name: "Tạm ngưng", exact: true }),
  ).toBeVisible();
  await logout(page);
  await login(page, "student");
  await page.goto(courseUrl);
  await page.getByText("Bài học E2E", { exact: true }).click();
  await expect(
    page.getByText("Nội dung chỉ dành cho học viên ACTIVE.", { exact: true }),
  ).toBeVisible();
  await logout(page);
  await login(page, "instructor");
  await page.goto(courseUrl);
  await page.getByRole("button", { name: "Tạm ngưng", exact: true }).click();
  await expect(
    page.getByRole("button", { name: "Kích hoạt", exact: true }),
  ).toBeVisible();
  await logout(page);
  await login(page, "student");
  await page.goto(courseUrl);
  await expect(
    page.getByText("Bạn chưa có quyền thực hiện thao tác này.", {
      exact: false,
    }),
  ).toBeVisible();
});

test("direct links and role guards; desktop and mobile views", async ({
  page,
}) => {
  await page.goto("/#/admin");
  await expect(
    page.getByRole("heading", { name: "Đăng nhập", exact: true }),
  ).toBeVisible();
  await page.screenshot({
    path: "test-results/week2-login.png",
    fullPage: true,
  });
  await login(page, "student");
  await expect(
    page.getByRole("heading", { name: "Khóa học của tôi" }),
  ).toBeVisible();
  await page.screenshot({
    path: "test-results/week2-student.png",
    fullPage: true,
  });
  await page.goto("/#/admin");
  await expect(
    page.getByRole("heading", { name: "Không có quyền truy cập" }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Về trang của tôi" }).click();
  await page.setViewportSize({ width: 390, height: 844 });
  await expect(
    page.getByRole("heading", { name: "Khóa học của tôi" }),
  ).toBeVisible();
  await page.screenshot({
    path: "test-results/week2-mobile.png",
    fullPage: true,
  });
  await expect(page.locator("body")).toHaveJSProperty("scrollWidth", 390);
  await page.reload();
  await expect(
    page.getByRole("heading", { name: "Đăng nhập", exact: true }),
  ).toBeVisible();
});

test("admin portal and rejected credentials", async ({ page }) => {
  await page.goto("/#/login");
  await page.getByLabel("Email hoặc tên đăng nhập").fill("demo_admin");
  await page.getByLabel("Mật khẩu", { exact: true }).fill("incorrect-password");
  await page.getByRole("button", { name: "Đăng nhập", exact: true }).click();
  await expect(page.locator("#messages")).toContainText("đăng nhập");
  await login(page, "admin");
  await expect(
    page.getByRole("link", { name: "Quản lý khóa học" }),
  ).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "Khóa học của bạn" }),
  ).toBeVisible();
});
