import {
  test,
  expect,
  type Page,
  type APIRequestContext,
} from "@playwright/test";

const password = process.env.LMS_DEMO_PASSWORD ?? "LmsDemo-Week2!2026";
async function login(page: Page, actor: string) {
  await page.goto("/#/login");
  await page.getByLabel("Email hoặc tên đăng nhập").fill("demo_" + actor);
  await page.getByLabel("Mật khẩu", { exact: true }).fill(password);
  await page.getByRole("button", { name: "Đăng nhập", exact: true }).click();
  await expect(page.getByRole("button", { name: "Đăng xuất" })).toBeVisible();
}

async function examFixture(request: APIRequestContext) {
  const base = "http://127.0.0.1:8013/api/v1";
  async function auth(actor: string) {
    const response = await request.post(base + "/auth/login", {
      data: { login: "demo_" + actor, password },
    });
    expect(response.ok()).toBeTruthy();
    return (await response.json()).data.access_token as string;
  }
  const instructor = await auth("instructor");
  const student = await auth("student");
  const call = async (
    path: string,
    method = "GET",
    data?: unknown,
    token = instructor,
  ) => {
    const response = await request.fetch(base + path, {
      method,
      data,
      headers: { Authorization: "Bearer " + token },
    });
    expect(response.ok()).toBeTruthy();
    return (await response.json()).data;
  };
  const learner = await call("/auth/me", "GET", undefined, student);
  const course = await call("/courses", "POST", {
    code: "W6_" + Date.now(),
    title: "Week 6 browser course",
  });
  const cid = course.id as string;
  const module = await call(`/courses/${cid}/modules`, "POST", {
    title: "Chapter",
  });
  await call(`/courses/${cid}/modules/${module.id}/lessons`, "POST", {
    title: "Lesson",
    lesson_type: "ARTICLE",
    content: "Content",
  });
  const bank = await call(`/courses/${cid}/question-banks`, "POST", {
    name: "Bank",
  });
  const question = await call(`/question-banks/${bank.id}/questions`, "POST", {
    question_type: "SINGLE",
    prompt: "2+2?",
    options: [
      { key: "A", text: "4", is_correct: true },
      { key: "B", text: "5" },
    ],
  });
  const exam = await call(`/courses/${cid}/exams`, "POST", {
    title: "Telemetry exam",
    opens_at: new Date(Date.now() - 60000).toISOString(),
    due_at: new Date(Date.now() + 3600000).toISOString(),
    duration_seconds: 600,
    questions: [{ question_id: question.id, position: 1, points: 10 }],
  });
  await call(`/courses/${cid}/status`, "POST", { status: "PUBLISHED" });
  await call(`/courses/${cid}/enrollments`, "POST", { student_id: learner.id });
  await call(`/courses/${cid}/enrollments/${learner.id}`, "PATCH", {
    status: "ACTIVE",
  });
  await call(`/exams/${exam.id}/publish`, "POST");
  return { cid, call };
}

test("Admin can filter audit records and Student route guard prevents audit requests", async ({
  page,
}) => {
  await login(page, "admin");
  await page
    .getByRole("link", { name: "Tài khoản & vai trò", exact: true })
    .click();
  const username = "audit_" + Date.now();
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
  await page
    .getByRole("link", { name: "Nhật ký kiểm toán", exact: true })
    .click();
  await page.getByLabel("Hành động", { exact: true }).fill("account.create");
  const filtered = page.waitForResponse(
    (response) =>
      response.url().includes("/audit/logs?") &&
      response.url().includes("action=account.create"),
  );
  await page.getByRole("button", { name: "Lọc nhật ký" }).click();
  await filtered;
  await expect(page.locator(".loading")).toHaveCount(0);
  await expect(
    page.getByRole("heading", { name: "account.create", exact: true }).first(),
  ).toBeVisible();
  await page.getByLabel("Hành động", { exact: true }).fill("no.such.action");
  await page.getByRole("button", { name: "Lọc nhật ký" }).click();
  await expect(page.getByText("Không có nhật ký phù hợp.")).toBeVisible();
  await page.getByRole("button", { name: "Đăng xuất" }).click();
  await login(page, "student");
  const requested: string[] = [];
  page.on("request", (request) => {
    if (request.url().includes("/audit/")) requested.push(request.url());
  });
  await page.goto("/#/admin/audit?trace_id=private");
  await expect(
    page.getByRole("heading", { name: "Không có quyền truy cập" }),
  ).toBeVisible();
  expect(requested).toEqual([]);
});

test("Student telemetry stops on navigation and Instructor reviews the flag", async ({
  page,
  request,
}) => {
  const { cid } = await examFixture(request);
  await login(page, "student");
  await page.goto(`/#/courses/${cid}`);
  await page
    .getByRole("button", { name: "Bắt đầu bài thi", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "Bài thi đang làm" }),
  ).toBeVisible();
  const saved = page.waitForResponse(
    (response) =>
      response.url().includes("/events") &&
      response.request().method() === "POST",
  );
  await page.evaluate(() => window.dispatchEvent(new Event("blur")));
  expect((await saved).status()).toBe(201);
  await page.goto("/#/student");
  await expect(page.locator(".attempt-box")).toHaveCount(0);
  const recorded: string[] = [];
  page.on("request", (request) => {
    if (request.url().includes("/events")) recorded.push(request.url());
  });
  await page.evaluate(() => window.dispatchEvent(new Event("blur")));
  await page.getByRole("button", { name: "Đăng xuất" }).click();
  expect(recorded).toEqual([]);
  await login(page, "instructor");
  await page.goto(`/#/courses/${cid}`);
  const review = page.locator(".attempt-review");
  await expect(review).toContainText("WINDOW_BLUR");
  await review.getByLabel("Kết quả xem xét").selectOption("DISMISSED");
  await review
    .getByLabel("Ghi chú xem xét")
    .fill("Đổi cửa sổ do nhầm thao tác");
  await review.getByRole("button", { name: "Lưu xem xét" }).click();
  await expect(review).toContainText("DISMISSED");
  await expect(review.getByRole("button", { name: "Lưu xem xét" })).toHaveCount(
    0,
  );
  await page.getByRole("button", { name: "Đăng xuất" }).click();
  await login(page, "admin");
  await page
    .getByRole("link", { name: "Sự kiện bảo mật", exact: true })
    .click();
  await page.getByLabel("Loại sự kiện").selectOption("LOGIN_SUCCEEDED");
  await page.getByRole("button", { name: "Lọc sự kiện" }).click();
  await expect(
    page.getByRole("heading", { name: "LOGIN_SUCCEEDED", exact: true }).first(),
  ).toBeVisible();
});
