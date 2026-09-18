import type {
  CatalogCourse,
  Course,
  CourseModule,
  CourseStaff,
  CurrentUser,
  Enrollment,
  MyEnrollment,
} from "../../../shared/contracts/api";
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
