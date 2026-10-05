import type {
  CurrentUser,
  UserPage,
  DashboardReport,
} from "../../../../../shared/contracts/api";
import { api } from "../../../services/api/client";
import { button, element, field } from "../../../components/dom";
import {
  actionForm,
  pagination,
  prefill,
  selectField,
  statistics,
  type PageActions,
} from "../../../components/forms";

const statuses: [string, string][] = [
  ["ACTIVE", "Hoạt động"],
  ["INACTIVE", "Chưa kích hoạt"],
  ["LOCKED", "Đã khóa"],
];
const roles: [string, string][] = [
  ["STUDENT", "Học viên"],
  ["INSTRUCTOR", "Giảng viên"],
  ["ADMIN", "Quản trị viên"],
];

export async function renderUsers(
  body: HTMLElement,
  actor: CurrentUser,
  query: URLSearchParams,
  actions: PageActions,
) {
  const search = query.get("search") ?? "";
  const status = query.get("status") ?? "";
  const offset = Math.max(0, Number(query.get("offset")) || 0);
  const [page, catalog] = await Promise.all([
    api.request<UserPage>(
      `/users?${new URLSearchParams({ search, ...(status ? { status } : {}), offset: String(offset), limit: "10" })}`,
    ),
    api.request<{ code: string; name: string }[]>("/roles"),
  ]);
  if (!actions.current()) return;
  const go = (offset: number, searchTerm = search, filter = status) =>
    actions.navigate(
      "/admin/users?" +
        new URLSearchParams({
          search: searchTerm,
          status: filter,
          offset: String(offset),
        }),
    );
  body.append(
    statistics([
      ["Tài khoản phù hợp", page.total],
      ["Vai trò", catalog.length],
    ]),
  );
  body.append(
    actionForm(
      [
        prefill(field("Tìm tài khoản", "search", "search", false), search),
        selectField(
          "Trạng thái tài khoản",
          "status",
          [["", "Tất cả"], ...statuses],
          status,
        ),
      ],
      "Lọc tài khoản",
      async (data) =>
        go(0, String(data.get("search")), String(data.get("status"))),
      actions.error,
    ),
  );
  const create = element("details", "", "panel");
  create.append(element("summary", "+ Tạo tài khoản"));
  create.append(
    actionForm(
      [
        field("Email mới", "email", "email"),
        field("Tên đăng nhập mới", "username"),
        field("Mật khẩu ban đầu", "password", "password"),
        selectField("Vai trò ban đầu", "role", roles),
      ],
      "Tạo tài khoản",
      (data) =>
        actions.perform(
          () =>
            api.request("/users", "POST", {
              email: data.get("email"),
              username: data.get("username"),
              password: data.get("password"),
              roles: [data.get("role")],
              status: "ACTIVE",
            }),
          "Đã tạo tài khoản.",
        ),
      actions.error,
    ),
  );
  body.append(create);
  if (!page.items.length)
    body.append(element("p", "Không có tài khoản phù hợp.", "empty"));
  for (const user of page.items) {
    const card = element("section", "", "panel user-card");
    card.dataset.userId = user.id;
    card.append(
      element("h2", user.username),
      element(
        "p",
        `${user.email} · ${statuses.find((s) => s[0] === user.status)?.[1] ?? user.status}`,
      ),
    );
    const isSelf = user.id === actor.id;
    const edit = element("details");
    edit.append(element("summary", "Sửa thông tin"));
    edit.append(
      actionForm(
        [
          prefill(field("Email", "email", "email"), user.email),
          prefill(field("Tên đăng nhập", "username"), user.username),
        ],
        "Lưu tài khoản",
        (data) =>
          actions.perform(
            () =>
              api.request(`/users/${user.id}`, "PUT", Object.fromEntries(data)),
            "Đã lưu tài khoản.",
          ),
        actions.error,
      ),
    );
    card.append(edit);
    if (!isSelf)
      card.append(
        actionForm(
          [selectField("Trạng thái mới", "status", statuses, user.status)],
          "Lưu trạng thái",
          (data) =>
            actions.perform(
              () =>
                api.request(`/auth/users/${user.id}/status`, "PATCH", {
                  status: data.get("status"),
                }),
              "Đã cập nhật trạng thái tài khoản.",
            ),
          actions.error,
        ),
      );
    const grants = element("div", "", "actions");
    for (const [code, label] of roles) {
      const has = user.roles.includes(code);
      const change = button(
        `${has ? "Gỡ" : "Gán"} ${label}`,
        () => {
          void actions.perform(
            () =>
              api.request(
                `/users/${user.id}/roles/${code}`,
                has ? "DELETE" : "PUT",
              ),
            "Đã cập nhật vai trò.",
          );
        },
        "button secondary",
      );
      change.disabled = isSelf && code === "ADMIN" && has;
      grants.append(change);
    }
    card.append(
      element(
        "p",
        `Vai trò: ${user.roles.map((code) => roles.find((r) => r[0] === code)?.[1] ?? code).join(", ") || "Chưa được phân quyền"}`,
      ),
      grants,
    );
    body.append(card);
  }
  body.append(pagination(page.offset, page.limit, page.total, go));
  const permissionBox = element("details", "", "panel");
  permissionBox.append(element("summary", "Quyền theo vai trò"));
  const permissions = await api.request<string[]>("/permissions");
  for (const role of catalog) {
    const current = await api.request<string[]>(
      `/roles/${role.code}/permissions`,
    );
    if (!actions.current()) return;
    const section = element("section");
    section.append(
      element("h3", roles.find((r) => r[0] === role.code)?.[1] ?? role.name),
    );
    for (const permission of permissions) {
      section.append(
        button(
          `${current.includes(permission) ? "Thu hồi" : "Cấp"} ${permission}`,
          () => {
            void actions.perform(
              () =>
                api.request(
                  `/roles/${role.code}/permissions/${permission}`,
                  current.includes(permission) ? "DELETE" : "PUT",
                ),
              "Đã cập nhật quyền.",
            );
          },
          "button secondary",
        ),
      );
    }
    permissionBox.append(section);
  }
  body.append(permissionBox);
}

export async function renderReports(
  body: HTMLElement,
  query: URLSearchParams,
  actions: PageActions,
) {
  const offset = Math.max(0, Number(query.get("offset")) || 0);
  const report = await api.request<DashboardReport>(
    `/reports/overview?limit=10&offset=${offset}`,
  );
  if (!actions.current()) return;
  const t = report.totals;
  body.append(
    statistics([
      ["Tài khoản", t.total_users],
      ["Hoạt động", t.active_users],
      ["Khóa học", t.total_courses],
      ["Ghi danh", t.enrollments],
      ["Đang học", t.active_enrollments],
      ["Đã hoàn thành", t.completed_learners],
    ]),
  );
  body.append(element("h2", "Báo cáo theo khóa học"));
  if (!report.courses.length)
    body.append(element("p", "Chưa có khóa học để báo cáo.", "empty"));
  const wrap = element("div", "", "table-scroll");
  const table = element("table", "", "report-table");
  const caption = element(
    "caption",
    "Ghi danh, hoàn thành và bài chờ chấm theo khóa học",
  );
  const head = element("thead");
  const row = element("tr");
  for (const label of [
    "Khóa học",
    "Trạng thái",
    "Ghi danh",
    "Đang học",
    "Hoàn thành",
    "Điểm nháp",
    "Bài nộp",
  ]) {
    const th = element("th", label);
    th.scope = "col";
    row.append(th);
  }
  head.append(row);
  const rows = element("tbody");
  for (const course of report.courses) {
    const row = element("tr");
    const title = element("td");
    const link = element("a", `${course.code} · ${course.title}`);
    link.href = `#/courses/${course.id}`;
    title.append(link);
    row.append(title);
    for (const value of [
      { DRAFT: "Bản nháp", PUBLISHED: "Đang mở", ARCHIVED: "Đã lưu trữ" }[
        course.status
      ],
      course.enrollments,
      course.active_enrollments,
      course.completed_learners,
      course.draft_grades,
      course.submissions,
    ])
      row.append(element("td", String(value)));
    rows.append(row);
  }
  table.append(caption, head, rows);
  wrap.append(table);
  body.append(wrap);
  body.append(
    pagination(offset, report.limit, report.total_courses, (n) =>
      actions.navigate(`/admin/reports?offset=${n}`),
    ),
  );
}
