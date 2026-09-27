import { chromium, expect } from "@playwright/test";

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
  await page.goto("http://127.0.0.1:5175");
  await page.getByLabel("Email hoặc tên đăng nhập").fill("demo_student");
  await page
    .getByLabel("Mật khẩu", { exact: true })
    .fill(process.env.LMS_DEMO_PASSWORD ?? "LmsDemo-Week2!2026");
  await page.getByRole("button", { name: "Đăng nhập", exact: true }).click();
  await expect(
    page.getByRole("heading", {
      name: "Lập trình web từ nền tảng",
      exact: true,
    }),
  ).toBeVisible();
  await page.screenshot({
    path: "test-results/showcase-desktop.png",
    fullPage: true,
  });
  const course = page
    .getByRole("article")
    .filter({
      has: page.getByRole("heading", {
        name: "Lập trình web từ nền tảng",
        exact: true,
      }),
    });
  await course.getByRole("button", { name: "Vào học", exact: true }).click();
  await expect(
    page.getByRole("heading", {
      name: "Xây dựng trang giới thiệu bản thân",
      exact: true,
    }),
  ).toBeVisible();
  await expect(
    page.getByText("37.5% hoàn thành", { exact: true }),
  ).toBeVisible();
  await expect(page.getByText("Lịch sử nộp", { exact: true })).toBeVisible();
  await page.screenshot({
    path: "test-results/showcase-course.png",
    fullPage: true,
  });
  await page.getByRole("link", { name: "Không gian học tập" }).click();
  await page.setViewportSize({ width: 390, height: 844 });
  await expect(
    page.getByRole("heading", {
      name: "Lập trình web từ nền tảng",
      exact: true,
    }),
  ).toBeVisible();
  await expect(page.locator("body")).toHaveJSProperty("scrollWidth", 390);
  await page.screenshot({
    path: "test-results/showcase-mobile.png",
    fullPage: true,
  });
  expect(failures).toEqual([]);
  console.log(
    "Showcase verified: courses, lessons, assignments, submission history, progress and mobile layout.",
  );
} finally {
  await browser.close();
}
