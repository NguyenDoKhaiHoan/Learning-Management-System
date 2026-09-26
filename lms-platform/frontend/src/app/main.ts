import type {
  Assignment,
  AssignmentInput,
  CatalogCourse,
  Course,
  CourseModule,
  CourseStaff,
  CurrentUser,
  Enrollment,
  MyEnrollment,
} from "../../../shared/contracts/api";

import { assignmentsApi } from "../features/assignments/services/assignments";

import { resourcesApi } from "../features/files/services/resources";

import { progressApi } from "../features/progress-analytics/services/progress";

import { api, ApiRequestError } from "../services/api/client";

import { guardRoute, homeFor } from "../routes/guard";

import { button, element, field } from "../components/dom";

import "../styles/main.css";

const root = document.querySelector<HTMLDivElement>("#app")!;

let user: CurrentUser | null = null;

let generation = 0;

let notice = "";

const labels: Record<string, string> = {
  DRAFT: "Bản nháp",

  PUBLISHED: "Đang mở",

  ARCHIVED: "Đã lưu trữ",

  PENDING: "Chờ duyệt",

  ACTIVE: "Đang học",

  SUSPENDED: "Tạm ngưng",

  COMPLETED: "Hoàn thành",

  ADMIN: "Quản trị viên",

  INSTRUCTOR: "Giảng viên",

  STUDENT: "Học viên",

  ASSISTANT: "Trợ giảng",

  CLOSED: "Đã đóng",

  SUBMITTED: "Đã nộp",

  LATE: "Nộp muộn",

  FILE: "Tệp",

  LINK: "Liên kết",
};

function navigate(path: string) {
  if (location.hash === "#" + path) void render();
  else location.hash = path;
}

function badge(status: string) {
  return element(
    "span",

    labels[status] ?? status,

    "badge " + status.toLowerCase(),
  );
}

function errorText(error: unknown) {
  if (!(error instanceof ApiRequestError))
    return "Có lỗi xảy ra. Vui lòng thử lại.";

  if (error.code === "LOGIN_FAILED")
    return "Thông tin đăng nhập không đúng hoặc tài khoản không hoạt động.";

  const messages: Record<number, string> = {
    401: "Phiên đăng nhập đã kết thúc. Hãy đăng nhập lại.",

    403: "Bạn chưa có quyền thực hiện thao tác này.",

    404: "Không tìm thấy dữ liệu yêu cầu.",

    409: "Thao tác chưa phù hợp: kiểm tra trạng thái, dữ liệu trùng và nội dung khóa học.",

    413: "Tệp vượt quá dung lượng cho phép.",

    422: "Kiểm tra lại các trường thông tin đã nhập.",
  };

  return (
    (messages[error.status] ?? error.message) +
    (error.traceId ? ` (Mã hỗ trợ: ${error.traceId})` : "")
  );
}

function showError(error: unknown) {
  const target = document.querySelector("#messages") ?? root;

  target.replaceChildren(element("p", errorText(error), "alert error"));

  target.setAttribute("role", "alert");
}

async function perform(action: () => Promise<unknown>, success: string) {
  try {
    await action();

    notice = success;

    await render();
  } catch (error) {
    showError(error);
  }
}

function form(
  fields: HTMLElement[],

  submitLabel: string,

  action: (data: FormData) => Promise<unknown>,
) {
  const node = element("form", "", "form-stack");

  const submit = element("button", submitLabel, "button");

  submit.type = "submit";

  node.append(...fields, submit);

  node.addEventListener("submit", async (event) => {
    event.preventDefault();

    if (submit.disabled) return;

    submit.disabled = true;

    try {
      await action(new FormData(node));
    } catch (error) {
      showError(error);
    } finally {
      submit.disabled = false;
    }
  });

  return node;
}

function textareaField(label: string, name: string, required = true) {
  const wrap = element("label", label, "field");

  const input = document.createElement("textarea");

  input.name = name;

  input.required = required;

  input.rows = 4;

  wrap.append(input);

  return wrap;
}

function checkboxField(label: string, name: string) {
  const wrap = element("label", "", "check-field");

  const input = document.createElement("input");

  input.type = "checkbox";

  input.name = name;

  wrap.append(input, document.createTextNode(label));

  return wrap;
}

function localDateTimeToIso(value: FormDataEntryValue | null) {
  const text = String(value ?? "").trim();

  return text ? new Date(text).toISOString() : null;
}

function toLocalDateTimeInput(value: string | null) {
  if (!value) return "";

  const date = new Date(value);

  const local = new Date(date.getTime() - date.getTimezoneOffset() * 60000);

  return local.toISOString().slice(0, 16);
}

function assignmentPayload(data: FormData): AssignmentInput {
  const allowLate = data.get("allow_late") === "on";

  return {
    title: String(data.get("title")),

    description: String(data.get("description")),

    opens_at: localDateTimeToIso(data.get("opens_at"))!,

    due_at: localDateTimeToIso(data.get("due_at"))!,

    allow_late: allowLate,

    late_until: allowLate ? localDateTimeToIso(data.get("late_until")) : null,

    max_attempts: Number(data.get("max_attempts") || 1),

    max_file_bytes: Number(data.get("max_file_bytes") || 10485760),

    allowed_mime_types: ["application/pdf"],

    max_score: Number(data.get("max_score") || 100),
  };
}

async function renderResources(
  target: HTMLElement,

  current: CurrentUser,

  course: Course,

  courseId: string,

  moduleId: string,

  lessonId: string,
) {
  const manager = current.roles.some(
    (role) => role === "ADMIN" || role === "INSTRUCTOR",
  );

  const resources = await resourcesApi.list(courseId, moduleId, lessonId);

  const box = element("div", "", "resource-box");

  box.append(element("strong", "Tài nguyên"));

  if (!resources.length) {
    box.append(element("p", "Chưa có tài nguyên.", "muted"));
  }

  for (const resource of resources) {
    const row = element("div", "", "list-row");

    row.append(
      element("span", resource.title),

      badge(resource.resource_type),
    );

    // ==========================

    // RESOURCE LINK

    // ==========================

    if (resource.resource_type === "LINK" && resource.url) {
      const link = element("a", "Mở liên kết", "button ghost");

      link.href = resource.url;

      link.target = "_blank";

      link.rel = "noopener noreferrer";

      row.append(link);
    }

    // ==========================
    // RESOURCE FILE
    // ==========================
    else if (resource.resource_type === "FILE") {
      row.append(
        button(
          "Tải tệp",

          () => {
            void resourcesApi

              .download(courseId, moduleId, lessonId, resource)

              .catch(showError);
          },

          "button ghost",
        ),
      );
    }

    // ==========================

    // DELETE RESOURCE

    // ==========================

    if (manager && course.status === "DRAFT") {
      row.append(
        button(
          "Xóa",

          () => {
            void perform(
              () =>
                resourcesApi.remove(courseId, moduleId, lessonId, resource.id),

              "Đã xóa tài nguyên.",
            );
          },

          "button ghost",
        ),
      );
    }

    box.append(row);
  }

  // ==========================

  // MANAGER CREATE RESOURCE

  // ==========================

  if (manager && course.status === "DRAFT") {
    box.append(
      // LINK

      form(
        [field("Tên liên kết", "title"), field("URL", "url", "url")],

        "Thêm liên kết",

        (data) =>
          perform(
            () =>
              resourcesApi.createLink(
                courseId,

                moduleId,

                lessonId,

                String(data.get("title")),

                String(data.get("url")),
              ),

            "Đã thêm liên kết.",
          ),
      ),

      // FILE

      form(
        [field("Tệp bài học", "file", "file")],

        "Upload tệp",

        async (data) => {
          const upload = data.get("file");

          if (!(upload instanceof File) || !upload.size) {
            throw new ApiRequestError(
              422,

              "VALIDATION_ERROR",

              "Chưa chọn tệp.",
            );
          }

          await perform(
            () => resourcesApi.upload(courseId, moduleId, lessonId, upload),

            "Đã upload tài nguyên.",
          );
        },
      ),
    );
  }

  target.append(box);
}

async function renderProgress(
  target: HTMLElement,

  current: CurrentUser,

  course: Course,

  courseId: string,
) {
  const manager = current.roles.some(
    (role) => role === "ADMIN" || role === "INSTRUCTOR",
  );

  const panel = element("section", "", "panel");

  panel.append(element("h2", "Tiến độ & điều kiện hoàn thành"));

  const rule = await progressApi.rule(courseId);

  panel.append(
    element(
      "p",

      `Yêu cầu bài học: ${rule.required_lesson_percent}%`,

      "muted",
    ),

    element(
      "p",

      rule.require_submitted_assignments
        ? "Yêu cầu nộp tất cả bài tập."
        : "Không bắt buộc bài tập để hoàn thành.",

      "muted",
    ),
  );

  // ==========================

  // INSTRUCTOR SET RULE

  // ==========================

  if (manager && course.status === "DRAFT") {
    const percent = field("Phần trăm lesson bắt buộc", "percent", "number");

    percent.querySelector("input")!.value = String(
      rule.required_lesson_percent,
    );

    const requireAssignments = checkboxField(
      "Yêu cầu nộp tất cả bài tập",

      "assignments",
    );

    requireAssignments.querySelector("input")!.checked =
      rule.require_submitted_assignments;

    panel.append(
      form(
        [percent, requireAssignments],

        "Lưu điều kiện hoàn thành",

        (data) =>
          perform(
            () =>
              progressApi.updateRule(
                courseId,

                Number(data.get("percent")),

                data.get("assignments") === "on",
              ),

            "Đã cập nhật điều kiện hoàn thành.",
          ),
      ),
    );
  }

  // ==========================
  // STUDENT PROGRESS
  // ==========================
  else if (!manager && current.roles.includes("STUDENT")) {
    const progress = await progressApi.mine(courseId);

    panel.append(
      element(
        "strong",

        `${progress.progress_percent}% hoàn thành`,
      ),

      element(
        "p",

        `Bài học: ` +
          `${progress.completed_lessons}` +
          `/${progress.total_lessons}` +
          ` · Bài tập: ` +
          `${progress.completed_assignments}` +
          `/${progress.total_assignments}`,

        "muted",
      ),
    );
  }

  target.append(panel);
}

async function renderAssignmentCard(
  target: HTMLElement,

  current: CurrentUser,

  course: Course,

  courseId: string,

  assignment: Assignment,
) {
  const manager = current.roles.some(
    (role) => role === "ADMIN" || role === "INSTRUCTOR",
  );

  const card = element("article", "", "panel");

  card.append(
    badge(assignment.status),

    element("h3", assignment.title),

    element("p", assignment.description),

    element(
      "p",

      `Mở: ${new Date(assignment.opens_at).toLocaleString()} · Hạn: ${new Date(
        assignment.due_at,
      ).toLocaleString()}`,

      "muted",
    ),

    element(
      "p",

      `Số lần nộp tối đa: ` +
        `${assignment.max_attempts}` +
        ` · Điểm tối đa: ` +
        `${assignment.max_score}`,

      "muted",
    ),
  );

  // =================================

  // INSTRUCTOR

  // =================================

  if (manager) {
    if (assignment.status === "DRAFT") {
      const editBox = element("details", "", "add-content");

      editBox.append(element("summary", "Chỉnh sửa bài tập"));

      const title = field("Tên bài tập", "title");

      title.querySelector("input")!.value = assignment.title;

      const description = textareaField("Mô tả", "description");

      description.querySelector("textarea")!.value = assignment.description;

      const opens = field("Mở lúc", "opens_at", "datetime-local");

      opens.querySelector("input")!.value = toLocalDateTimeInput(
        assignment.opens_at,
      );

      const due = field("Hạn nộp", "due_at", "datetime-local");

      due.querySelector("input")!.value = toLocalDateTimeInput(
        assignment.due_at,
      );

      const allowLate = checkboxField("Cho phép nộp muộn", "allow_late");

      allowLate.querySelector("input")!.checked = assignment.allow_late;

      const lateUntil = field(
        "Hạn nộp muộn",

        "late_until",

        "datetime-local",

        false,
      );

      lateUntil.querySelector("input")!.value = toLocalDateTimeInput(
        assignment.late_until,
      );

      const attempts = field("Số lần nộp tối đa", "max_attempts", "number");

      attempts.querySelector("input")!.value = String(assignment.max_attempts);

      const maxBytes = field("Dung lượng tối đa", "max_file_bytes", "number");

      maxBytes.querySelector("input")!.value = String(
        assignment.max_file_bytes,
      );

      const score = field("Điểm tối đa", "max_score", "number");

      score.querySelector("input")!.value = String(assignment.max_score);

      editBox.append(
        form(
          [
            title,

            description,

            opens,

            due,

            allowLate,

            lateUntil,

            attempts,

            maxBytes,

            score,
          ],

          "Lưu thay đổi",

          (data) => {
            const payload = assignmentPayload(data);

            // Giữ policy MIME hiện tại.

            payload.allowed_mime_types = assignment.allowed_mime_types;

            return perform(
              () => assignmentsApi.update(courseId, assignment.id, payload),

              "Đã cập nhật bài tập.",
            );
          },
        ),
      );

      card.append(editBox);

      if (course.status === "PUBLISHED") {
        card.append(
          button("Công bố", () => {
            void perform(
              () =>
                assignmentsApi.transition(courseId, assignment.id, "PUBLISHED"),
              "Đã công bố bài tập.",
            );
          }),
        );
      } else {
        card.append(
          element(
            "p",
            "Hãy công bố khóa học trước khi công bố bài tập.",
            "muted",
          ),
        );
      }

      card.append(
        button(
          "Xóa",
          () => {
            void perform(
              () => assignmentsApi.remove(courseId, assignment.id),
              "Đã xóa bài tập.",
            );
          },
          "button ghost",
        ),
      );
    } else if (assignment.status === "PUBLISHED") {
      card.append(
        button(
          "Đóng bài tập",

          () => {
            void perform(
              () =>
                assignmentsApi.transition(courseId, assignment.id, "CLOSED"),

              "Đã đóng bài tập.",
            );
          },

          "button secondary",
        ),
      );
    } else if (assignment.status === "CLOSED") {
      card.append(
        button(
          "Lưu trữ",

          () => {
            void perform(
              () =>
                assignmentsApi.transition(courseId, assignment.id, "ARCHIVED"),

              "Đã lưu trữ bài tập.",
            );
          },

          "button secondary",
        ),
      );
    }

    // =================================

    // INSTRUCTOR VIEW SUBMISSION

    // =================================

    const submissions = await assignmentsApi.submissions(
      courseId,

      assignment.id,
    );

    const history = element("details", "", "submission-history");

    history.append(
      element(
        "summary",

        `Bài nộp (${submissions.length})`,
      ),
    );

    for (const submission of submissions) {
      const row = element("div", "", "list-row");

      row.append(
        element(
          "span",

          `SV #${submission.student_id}` +
            ` · Version ` +
            `${submission.version}`,
        ),

        badge(submission.status),
      );

      const files = await assignmentsApi.files(
        courseId,

        assignment.id,

        submission.id,
      );

      for (const file of files) {
        row.append(
          button(
            file.title,

            () => {
              void assignmentsApi

                .downloadFile(courseId, assignment.id, submission.id, file)

                .catch(showError);
            },

            "button ghost",
          ),
        );
      }

      history.append(row);
    }

    card.append(history);
  }

  // =================================
  // STUDENT
  // =================================
  else if (current.roles.includes("STUDENT")) {
    if (assignment.status === "PUBLISHED") {
      // SUBMIT TEXT

      card.append(
        form(
          [textareaField("Câu trả lời", "answer_text")],

          "Nộp bài dạng text",

          (data) =>
            perform(
              () =>
                assignmentsApi.submitText(
                  courseId,

                  assignment.id,

                  String(data.get("answer_text")),
                ),

              "Đã nộp bài.",
            ),
        ),
      );

      // SUBMIT FILE

      const fileControl = field("Bài làm PDF", "file", "file");

      fileControl.querySelector("input")!.accept =
        assignment.allowed_mime_types.join(",");

      card.append(
        form(
          [fileControl],

          "Nộp tệp",

          async (data) => {
            const upload = data.get("file");

            if (!(upload instanceof File) || !upload.size) {
              throw new ApiRequestError(
                422,

                "VALIDATION_ERROR",

                "Chưa chọn tệp.",
              );
            }

            await perform(
              () => assignmentsApi.submitFile(courseId, assignment.id, upload),

              "Đã nộp tệp.",
            );
          },
        ),
      );
    }

    // =================================

    // STUDENT SUBMISSION HISTORY

    // =================================

    const mine = await assignmentsApi.mine(courseId, assignment.id);

    if (mine.length) {
      const history = element("div", "", "submission-history");

      history.append(element("strong", "Lịch sử nộp"));

      for (const submission of mine) {
        history.append(
          element(
            "p",

            `Version ` +
              `${submission.version}` +
              ` · ` +
              `${labels[submission.status] ?? submission.status}` +
              ` · ` +
              `${new Date(submission.submitted_at).toLocaleString()}`,

            "muted",
          ),
        );
      }

      card.append(history);
    }
  }

  target.append(card);
}

async function renderAssignments(
  target: HTMLElement,

  current: CurrentUser,

  course: Course,

  courseId: string,
) {
  const manager = current.roles.some(
    (role) => role === "ADMIN" || role === "INSTRUCTOR",
  );

  const section = element("section");

  section.append(element("h2", "Bài tập"));

  // =================================

  // CREATE ASSIGNMENT

  // =================================

  if (manager && course.status !== "ARCHIVED") {
    section.append(
      form(
        [
          field("Tên bài tập", "title"),

          textareaField("Mô tả", "description"),

          field("Mở lúc", "opens_at", "datetime-local"),

          field("Hạn nộp", "due_at", "datetime-local"),

          checkboxField("Cho phép nộp muộn", "allow_late"),

          field("Hạn nộp muộn", "late_until", "datetime-local", false),

          field("Số lần nộp tối đa", "max_attempts", "number"),

          field("Dung lượng tối đa (bytes)", "max_file_bytes", "number"),

          field("Điểm tối đa", "max_score", "number"),
        ],

        "Tạo bài tập",

        (data) =>
          perform(
            () => assignmentsApi.create(courseId, assignmentPayload(data)),

            "Đã tạo bài tập.",
          ),
      ),
    );
  }

  const assignments = await assignmentsApi.list(courseId);

  if (!assignments.length) {
    section.append(element("p", "Chưa có bài tập.", "empty"));
  }

  for (const assignment of assignments) {
    await renderAssignmentCard(section, current, course, courseId, assignment);
  }

  target.append(section);
}

function shell(title: string, subtitle: string, showNotice = true) {
  root.replaceChildren();

  const layout = element("div", "", "workspace");

  const aside = element("aside", "", "sidebar");

  const brand = element("div", "", "brand");

  brand.append(element("span", "L", "brand-mark"), element("strong", "LMS"));

  const nav = element("nav");

  nav.setAttribute("aria-label", "Điều hướng chính");

  if (user) {
    const items: [string, string, string][] = [
      ["ADMIN", "/admin", "Quản lý khóa học"],

      ["INSTRUCTOR", "/instructor", "Lớp tôi giảng dạy"],

      ["STUDENT", "/student", "Không gian học tập"],
    ];

    for (const [role, path, label] of items)
      if (user.roles.includes(role)) {
        const link = element(
          "a",

          label,

          location.hash === "#" + path ? "nav-link active" : "nav-link",
        );

        link.href = "#" + path;

        nav.append(link);
      }
  }

  aside.append(brand, element("p", "KHÔNG GIAN CỦA BẠN", "eyebrow"), nav);

  const profile = element("div", "", "profile");

  if (user)
    profile.append(
      element("strong", user.username),

      element("small", user.roles.map((r) => labels[r] ?? r).join(" · ")),

      button(
        "Đăng xuất",

        () => {
          void api.logout().catch(showError);
        },

        "button ghost",
      ),
    );

  aside.append(profile);

  const main = element("main");

  const header = element("header", "", "page-header");

  const text = element("div");

  text.append(
    element("p", "HỌC TẬP MỖI NGÀY", "eyebrow"),

    element("h1", title),

    element("p", subtitle, "muted"),
  );

  header.append(text);

  const messages = element("div");

  messages.id = "messages";

  messages.setAttribute("aria-live", "polite");

  if (notice && showNotice) {
    messages.append(element("p", notice, "alert success"));

    notice = "";
  }

  const body = element("div");

  body.id = "page-body";

  main.append(header, messages, body);

  layout.append(aside, main);

  root.append(layout);

  return body;
}

function loginPage() {
  root.replaceChildren();

  const page = element("main", "", "login-page");

  const story = element("section", "", "login-story");

  story.append(
    element("div", "LMS / LEARNING SPACE", "eyebrow"),

    element("h1", "Một nơi để học.\nNhiều điều để khám phá."),

    element(
      "p",

      "Kết nối với lớp học, khám phá kiến thức và chủ động trên hành trình của bạn.",
    ),

    element(
      "div",

      "01  Khám phá     /     02  Kết nối     /     03  Học tập",

      "story-footer",
    ),
  );

  const panel = element("section", "", "login-panel");

  panel.append(
    element("p", "CHÀO MỪNG TRỞ LẠI", "eyebrow"),

    element("h2", "Đăng nhập"),

    element("p", "Tiếp tục cùng không gian học tập của bạn.", "muted"),
  );

  const messages = element("div");

  messages.id = "messages";

  messages.setAttribute("aria-live", "polite");

  panel.append(messages);

  if (notice) {
    messages.append(element("p", notice, "alert"));

    notice = "";
  }

  const login = field("Email hoặc tên đăng nhập", "login");

  login.querySelector("input")!.autocomplete = "username";

  const password = field("Mật khẩu", "password", "password");

  password.querySelector("input")!.autocomplete = "current-password";

  panel.append(
    form([login, password], "Đăng nhập", async (data) => {
      user = await api.login(
        String(data.get("login")),

        String(data.get("password")),
      );

      navigate(homeFor(user));
    }),
  );

  page.append(story, panel);

  root.append(page);
}

function card(
  course: CatalogCourse,

  action: HTMLElement,

  status = "PUBLISHED",
) {
  const node = element("article", "", "course-card");

  const cover = element("div", "", "course-cover");

  cover.append(
    element("span", course.code, "course-code"),

    element("span", "↗", "cover-symbol"),
  );

  const content = element("div", "", "card-body");

  content.append(
    badge(status),

    element("h3", course.title),

    element(
      "p",

      course.description || "Khám phá nội dung cùng giảng viên.",

      "muted",
    ),

    action,
  );

  node.append(cover, content);

  return node;
}

async function dashboard(
  body: HTMLElement,

  current: CurrentUser,

  serial: number,
) {
  const student = location.hash === "#/student";

  const courses = await api.request<(Course | CatalogCourse)[]>(
    student ? "/catalog/courses?limit=100" : "/courses?limit=100",
  );

  const enrollments = student
    ? await api.request<MyEnrollment[]>("/enrollments/me?limit=100")
    : [];

  if (serial !== generation) return;

  const strip = element("div", "", "intro-strip");

  strip.append(
    element("strong", `Xin chào, ${current.username}.`),

    element(
      "span",

      student
        ? "Chọn một khóa học để bắt đầu hôm nay."
        : "Mọi lớp học và học viên, trong cùng một không gian.",
    ),
  );

  body.append(strip);

  if (student) {
    body.append(element("h2", "Khóa học của tôi"));

    const enrolled = element("div", "", "enrollment-list");

    if (!enrollments.length)
      enrolled.append(element("p", "Bạn chưa ghi danh khóa học nào.", "empty"));

    for (const item of enrollments) {
      const row = element("div", "", "list-row");

      row.append(
        element("strong", item.title ?? "Khóa học"),

        badge(item.status),
      );

      if (item.status === "ACTIVE" && item.course_status === "PUBLISHED")
        row.append(
          button(
            "Vào học",

            () => navigate("/courses/" + item.course_id),

            "button secondary",
          ),
        );

      enrolled.append(row);
    }

    body.append(enrolled, element("h2", "Khám phá khóa học"));
  } else {
    const create = element("details", "", "panel");

    create.append(element("summary", "+ Tạo khóa học mới"));

    create.append(
      form(
        [
          field("Mã khóa học", "code"),

          field("Tên khóa học", "title"),

          field("Mô tả", "description", "text", false),
        ],

        "Tạo khóa học",

        async (data) => {
          const course = await api.request<Course>(
            "/courses",

            "POST",

            Object.fromEntries(data),
          );

          notice = "Đã tạo khóa học. Thêm bài học trước khi công bố.";

          navigate("/courses/" + course.id);
        },
      ),
    );

    body.append(create);
  }

  const grid = element("div", "", "course-grid");

  if (!courses.length)
    grid.append(
      element(
        "p",

        student
          ? "Chưa có khóa học đang mở."
          : "Chưa có khóa học. Hãy tạo lớp học đầu tiên.",

        "empty",
      ),
    );

  for (const course of courses) {
    const enrollment = enrollments.find((e) => e.course_id === course.id);

    let action: HTMLElement;

    if (student && !enrollment)
      action = button("Gửi yêu cầu ghi danh", () => {
        const b = action as HTMLButtonElement;

        b.disabled = true;

        void perform(
          () => api.request(`/courses/${course.id}/enrollments`, "POST", {}),

          "Đã gửi yêu cầu. Hãy chờ giảng viên duyệt.",
        ).finally(() => {
          b.disabled = false;
        });
      });
    else if (!student || enrollment?.status === "ACTIVE")
      action = button(
        student ? "Vào học" : "Quản lý khóa học",

        () => navigate("/courses/" + course.id),

        "button secondary",
      );
    else action = element("p", labels[enrollment!.status], "muted");

    grid.append(
      card(course, action, "status" in course ? course.status : "PUBLISHED"),
    );
  }

  body.append(grid);
}

async function coursePage(
  body: HTMLElement,

  current: CurrentUser,

  cid: string,

  serial: number,
) {
  const course = await api.request<Course>(`/courses/${cid}`);

  const modules = await api.request<CourseModule[]>(`/courses/${cid}/modules`);

  if (serial !== generation) return;

  const manager = current.roles.some(
    (r) => r === "ADMIN" || r === "INSTRUCTOR",
  );

  document.querySelector("h1")!.textContent = course.title;

  const back = element("a", "← Về danh sách", "back-link");

  back.href = "#" + homeFor(current);

  body.append(back);

  const overview = element("div", "", "intro-strip");

  overview.append(
    badge(course.status),

    element(
      "p",

      course.description || "Cùng bắt đầu khám phá nội dung khóa học.",
    ),
  );

  body.append(overview);

  if (manager) {
    const actions = element("div", "", "actions");

    for (const [status, label] of course.status === "DRAFT"
      ? [["PUBLISHED", "Công bố khóa học"]]
      : [["DRAFT", "Chuyển về bản nháp"]]) {
      actions.append(
        button(label, () => {
          void perform(
            () => api.request(`/courses/${cid}/status`, "POST", { status }),

            "Đã cập nhật trạng thái khóa học.",
          );
        }),
      );
    }

    body.append(actions);
  }

  const columns = element("div", "", manager ? "course-columns" : "");

  const content = element("section");

  content.append(element("h2", "Nội dung học tập"));

  if (!modules.length)
    content.append(element("p", "Khóa học chưa có bài học.", "empty"));

  for (const module of modules) {
    const section = element("section", "", "panel");

    section.append(
      element(
        "h3",

        `${module.position.toString().padStart(2, "0")}  ${module.title}`,
      ),
    );

    for (const lesson of module.lessons) {
      const details = element("details", "", "lesson");

      details.append(
        element("summary", lesson.title),

        element(
          "p",

          lesson.content ?? "Nội dung đang được chuẩn bị.",

          "lesson-text",
        ),
      );

      // =================================

      // STUDENT UPDATE PROGRESS

      // =================================

      if (!manager && current.roles.includes("STUDENT")) {
        details.append(
          button(
            "Đánh dấu hoàn thành",

            () => {
              void perform(
                () => progressApi.updateLesson(cid, lesson.id, "COMPLETED", 0),

                "Đã cập nhật tiến độ bài học.",
              );
            },

            "button secondary",
          ),
        );
      }

      // =================================

      // WEEK 3 RESOURCE

      // =================================

      await renderResources(
        details,

        current,

        course,

        cid,

        module.id,

        lesson.id,
      );

      section.append(details);
    }

    if (manager && course.status === "DRAFT") {
      const add = element("details", "", "add-content");

      add.append(element("summary", "+ Thêm bài học"));

      add.append(
        form(
          [field("Tên bài học", "title"), field("Nội dung bài học", "content")],

          "Lưu bài học",

          (data) =>
            perform(
              () =>
                api.request(
                  `/courses/${cid}/modules/${module.id}/lessons`,

                  "POST",

                  { ...Object.fromEntries(data), lesson_type: "ARTICLE" },
                ),

              "Đã thêm bài học.",
            ),
        ),
      );

      section.append(add);
    }

    content.append(section);
  }

  if (manager && course.status === "DRAFT")
    content.append(
      form([field("Tên chương mới", "title")], "Thêm chương", (data) =>
        perform(
          () =>
            api.request(
              `/courses/${cid}/modules`,

              "POST",

              Object.fromEntries(data),
            ),

          "Đã thêm chương.",
        ),
      ),
    );

  columns.append(content);

  body.append(columns);

  await renderProgress(body, current, course, cid);

  await renderAssignments(body, current, course, cid);

  if (manager) {
    const enrollments = await api.request<Enrollment[]>(
      `/courses/${cid}/enrollments?limit=100`,
    );

    const staff = await api.request<CourseStaff[]>(`/courses/${cid}/staff`);

    if (serial !== generation) return;

    const side = element("section");

    side.append(element("h2", "Ghi danh"));

    if (!enrollments.length)
      side.append(element("p", "Chưa có yêu cầu ghi danh.", "empty"));

    for (const enrollment of enrollments) {
      const row = element("div", "", "panel enrollment-row");

      row.append(
        element("strong", "Học viên #" + enrollment.student_id),

        badge(enrollment.status),
      );

      if (["PENDING", "ACTIVE", "SUSPENDED"].includes(enrollment.status)) {
        const status = enrollment.status === "ACTIVE" ? "SUSPENDED" : "ACTIVE";

        row.append(
          button(
            status === "ACTIVE" ? "Kích hoạt" : "Tạm ngưng",

            () => {
              void perform(
                () =>
                  api.request(
                    `/courses/${cid}/enrollments/${enrollment.student_id}`,

                    "PATCH",

                    { status },
                  ),

                "Đã cập nhật ghi danh.",
              );
            },

            "button secondary",
          ),
        );
      }

      side.append(row);
    }

    side.append(element("h2", "Đội ngũ giảng dạy"));

    for (const person of staff) {
      const row = element("div", "", "list-row");

      row.append(element("span", person.username), badge(person.role));

      if (current.roles.includes("ADMIN"))
        row.append(
          button(
            "Gỡ phân công",

            () => {
              void perform(
                () =>
                  api.request(
                    `/courses/${cid}/staff/${person.user_id}`,

                    "DELETE",
                  ),

                "Đã gỡ phân công.",
              );
            },

            "button ghost",
          ),
        );

      side.append(row);
    }

    if (current.roles.includes("ADMIN"))
      side.append(
        form(
          [field("Mã giảng viên", "user_id", "number")],

          "Phân công giảng viên",

          (data) =>
            perform(
              () =>
                api.request(
                  `/courses/${cid}/staff/${encodeURIComponent(String(data.get("user_id")))}`,

                  "PUT",

                  { role: "INSTRUCTOR" },
                ),

              "Đã phân công giảng viên.",
            ),
        ),
      );

    columns.append(side);
  }
}

async function render() {
  const serial = ++generation;

  const path = location.hash.slice(1) || "/login";

  if (path === "/login") {
    loginPage();

    return;
  }

  if (!api.authenticated) {
    user = null;

    navigate("/login");

    return;
  }

  const body = shell(
    "Không gian học tập",

    "Khóa học, bài học và kết nối của bạn.",

    false,
  );

  body.append(element("p", "Đang tải…", "loading"));

  try {
    user = await api.request<CurrentUser>("/auth/me");

    if (serial !== generation) return;

    if (guardRoute(path, user) === "forbidden") {
      const denied = shell(
        "Không có quyền truy cập",

        "Tài khoản hiện tại không có quyền vào trang này.",
      );

      denied.append(button("Về trang của tôi", () => navigate(homeFor(user!))));

      return;
    }

    if (path === "/forbidden") {
      shell(
        "Chưa được phân quyền",

        "Liên hệ quản trị viên để được cấp vai trò phù hợp.",
      );

      return;
    }

    const target = shell(
      path === "/student" ? "Hôm nay, bạn muốn học gì?" : "Khóa học của bạn",

      "Mỗi bài học là một bước tiến mới.",
    );

    const course = /^\/courses\/(\d+)$/.exec(path);

    if (course) await coursePage(target, user, course[1], serial);
    else if (["/admin", "/instructor", "/student"].includes(path))
      await dashboard(target, user, serial);
    else target.append(element("p", "Trang không tồn tại.", "empty"));
  } catch (error) {
    if (serial === generation) {
      document.querySelector(".loading")?.remove();

      showError(error);
    }
  }
}

api.onSessionLost = () => {
  user = null;

  notice = "Bạn đã đăng xuất. Hãy đăng nhập để tiếp tục.";

  navigate("/login");
};

window.addEventListener("hashchange", () => {
  void render();
});

void render();
