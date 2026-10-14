import {
  test,
  expect,
  type Page,
  type APIRequestContext,
} from "@playwright/test";
import { readFile } from "node:fs/promises";

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
  return {
    cid,
    call,
    examId: exam.id as string,
    question,
    studentCall: (path: string, method = "GET", data?: unknown) =>
      call(path, method, data, student),
  };
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

test("Instructor filters course reports and downloads a gradebook; Admin exports overview", async ({
  page,
  request,
}) => {
  const { cid, call, examId, question, studentCall } =
    await examFixture(request);
  const attempt = await studentCall(`/exams/${examId}/attempts`, "POST");
  await studentCall(`/attempts/${attempt.id}/answers/${question.id}`, "PUT", {
    selected_option_ids: [question.options[0].id],
    expected_version: 0,
  });
  await studentCall(`/attempts/${attempt.id}/submit`, "POST");
  const grade = (await call(`/courses/${cid}/grades`))[0];
  await call(`/grades/${grade.id}/publish`, "POST", {
    expected_version: grade.version,
  });
  await login(page, "instructor");
  await page.goto(`/#/courses/${cid}`);
  const reports = page.locator(".course-reports");
  await expect(
    reports.getByRole("table", { name: "Tiến độ học viên" }),
  ).toContainText("demo_student");
  await expect(
    reports.getByRole("table", { name: "Gradebook theo bộ lọc" }),
  ).toContainText("Telemetry exam");
  await reports
    .getByLabel("Tìm học viên trong báo cáo")
    .fill("no-such-student");
  await reports
    .getByRole("button", { name: "Lọc báo cáo", exact: true })
    .click();
  await expect(reports.getByText("Không có học viên phù hợp.")).toBeVisible();
  await reports.getByLabel("Tìm học viên trong báo cáo").fill("");
  await reports
    .getByRole("button", { name: "Lọc báo cáo", exact: true })
    .click();
  await expect(
    reports.getByRole("table", { name: "Gradebook theo bộ lọc" }),
  ).toContainText("demo_student");
  async function exportCsv(label: string) {
    const created = page.waitForResponse(
      (response) =>
        response.url().endsWith("/exports") &&
        response.request().method() === "POST",
    );
    await page.getByRole("button", { name: label, exact: true }).click();
    const job = (await (await created).json()).data;
    const row = page.locator(`.export-job[data-job-id="${job.id}"]`);
    await expect(row).toContainText("Sẵn sàng tải", { timeout: 15000 });
    const downloading = page.waitForEvent("download");
    await row.getByRole("button", { name: "Tải CSV", exact: true }).click();
    const downloaded = await downloading;
    expect(downloaded.suggestedFilename()).toContain(".csv");
    return readFile((await downloaded.path())!, "utf8");
  }
  const gradebook = await exportCsv("Xuất gradebook CSV");
  expect(gradebook).toContain("grade_id,enrollment_id,student_id");
  expect(gradebook).toContain("demo_student");
  expect(gradebook).toContain("PUBLISHED");
  await page.getByRole("button", { name: "Đăng xuất" }).click();
  await login(page, "admin");
  await page
    .getByRole("link", { name: "Báo cáo tổng quan", exact: true })
    .click();
  expect(await exportCsv("Xuất tổng quan CSV")).toContain(
    "Week 6 browser course",
  );
});

test("Student submits assignment versions, resumes saved exam answers and sees only published grades", async ({
  page,
  request,
}) => {
  const { cid, call, examId, studentCall } = await examFixture(request);
  const assignment = await call(`/courses/${cid}/assignments`, "POST", {
    title: "Acceptance assignment",
    description: "Submit text and PDF versions",
    opens_at: new Date(Date.now() - 60000).toISOString(),
    due_at: new Date(Date.now() + 3600000).toISOString(),
    max_attempts: 2,
    max_file_bytes: 1024,
    allowed_mime_types: ["application/pdf"],
    max_score: 100,
  });
  const assignmentPath = `/courses/${cid}/assignments/${assignment.id}`;
  await call(assignmentPath + "/status", "POST", { status: "PUBLISHED" });
  await login(page, "student");
  await page.goto(`/#/courses/${cid}`);
  await page.getByLabel("Câu trả lời", { exact: true }).fill("Bài làm nghiệm thu");
  await page.getByRole("button", { name: "Nộp bài dạng text", exact: true }).click();
  await expect(page.getByText(/Version 1 · Đã nộp/)).toBeVisible();
  await page.getByLabel("Bài làm PDF", { exact: true }).setInputFiles({
    name: "acceptance.pdf",
    mimeType: "application/pdf",
    buffer: Buffer.from("%PDF-1.7\nAcceptance submission"),
  });
  await page.getByRole("button", { name: "Nộp tệp", exact: true }).click();
  await expect(page.getByText(/Version 2 · Đã nộp/)).toBeVisible();
  await expect(page.getByText(/Version 1 · Đã nộp/)).toBeVisible();
  await page.getByRole("button", { name: "Bắt đầu bài thi", exact: true }).click();
  const saved = page.waitForResponse((response) =>
    response.url().includes("/answers/") && response.request().method() === "PUT",
  );
  await page.getByRole("radio", { name: "4", exact: true }).check();
  expect((await saved).status()).toBe(200);
  const eligibility = await studentCall(`/exams/${examId}/eligibility`);
  const attemptPath = `/attempts/${eligibility.active_attempt_id}`;
  const before = await studentCall(attemptPath);
  await page.goto("/#/student");
  await expect(page.getByRole("heading", { name: "Khóa học của tôi" })).toBeVisible();
  await page.goto(`/#/courses/${cid}`);
  await page.getByRole("button", { name: "Tiếp tục bài thi", exact: true }).click();
  await expect(page.getByRole("radio", { name: "4", exact: true })).toBeChecked();
  expect((await studentCall(attemptPath)).expires_at).toBe(before.expires_at);
  await page.getByRole("button", { name: "Nộp bài thi", exact: true }).click();
  await expect(page.getByText("Đã nộp bài thi.", { exact: true })).toBeVisible();
  await expect(page.locator(".student-grades")).toContainText("Chưa có điểm được công bố.");
  const submissions = await studentCall(assignmentPath + "/submissions/mine");
  expect(submissions.map((submission: { version: number }) => submission.version)).toEqual([1, 2]);
  await call(`/courses/${cid}/grades`, "POST", {
    enrollment_id: submissions[1].enrollment_id,
    assessment_type: "ASSIGNMENT",
    assessment_id: assignment.id,
    source_id: submissions[1].id,
    feedback: "Đạt yêu cầu nghiệm thu",
    items: [{ item_key: "overall", label: "Essay", score: 85, max_score: 100 }],
  });
  const grades = await call(`/courses/${cid}/grades`);
  expect(grades).toHaveLength(2);
  for (const grade of grades) {
    await call(`/grades/${grade.id}/publish`, "POST", { expected_version: grade.version });
  }
  await page.goto("/#/student");
  await expect(page.getByRole("heading", { name: "Khóa học của tôi" })).toBeVisible();
  await page.goto(`/#/courses/${cid}`);
  await expect(page.locator(".student-grades .grade-card")).toHaveCount(2);
  await expect(page.locator(".student-grades")).toContainText("85.00/100.00 (85%)");
  await expect(page.locator(".student-grades")).toContainText("10.00/10.00 (100%)");
  await expect(page.locator(".student-grades")).toContainText("Nhận xét: Đạt yêu cầu nghiệm thu");
});
