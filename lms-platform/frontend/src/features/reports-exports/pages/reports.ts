import { api } from "../../../services/api/client";
import { button, element, field } from "../../../components/dom";
import {
  actionForm,
  pagination,
  selectField,
  statistics,
  type PageActions,
} from "../../../components/forms";

interface ExportJob {
  id: string;
  kind: string;
  course_id: string | null;
  status: string;
  row_count: number | null;
  error_code: string | null;
}
type ExportChoice = {
  label: string;
  kind: string;
  course_id?: string;
  filters?: Record<string, string>;
};

export async function renderExports(
  body: HTMLElement,
  actions: PageActions,
  choices: () => ExportChoice[],
) {
  const section = element("section", "", "panel exports-section");
  section.append(
    element("h2", "Xuất dữ liệu"),
    element(
      "p",
      "Yêu cầu được xử lý nền. Khi hoàn tất, bạn có thể tải CSV của mình.",
      "muted",
    ),
  );
  const controls = element("div", "", "actions");
  for (const choice of choices()) {
    const control = button(
      choice.label,
      () => {
        control.disabled = true;
        const latest = choices().find((item) => item.kind === choice.kind)!;
        void api
          .request<ExportJob>("/exports", "POST", {
            ...latest,
            label: undefined,
            request_id: crypto.randomUUID(),
          })
          .then(async () => {
            offset = 0;
            await load();
          })
          .catch(actions.error)
          .finally(() => {
            control.disabled = false;
          });
      },
      "button secondary",
    );
    controls.append(control);
  }
  section.append(controls);
  const list = element("div");
  section.append(list);
  body.append(section);
  let offset = 0;
  let poll = 0;
  let revision = 0;
  const load = async () => {
    const serial = ++revision;
    window.clearTimeout(poll);
    const page = await api.request<{
      items: ExportJob[];
      total: number;
      limit: number;
    }>(`/exports?limit=10&offset=${offset}`);
    if (!actions.current() || serial !== revision) return;
    list.replaceChildren();
    if (!page.items.length)
      list.append(element("p", "Chưa có yêu cầu xuất dữ liệu.", "empty"));
    for (const job of page.items) {
      const row = element("article", "", "panel export-job");
      row.dataset.jobId = job.id;
      const kind =
        {
          OVERVIEW: "Tổng quan",
          LEARNERS: "Tiến độ học viên",
          GRADEBOOK: "Gradebook",
        }[job.kind] ?? job.kind;
      const state =
        {
          PENDING: "Đang xử lý",
          READY: "Sẵn sàng tải",
          FAILED: "Xuất dữ liệu thất bại",
        }[job.status] ?? job.status;
      row.append(
        element("h3", `${kind} #${job.id}`),
        element(
          "p",
          `${state}${job.row_count !== null ? ` · ${job.row_count} dòng` : ""}${job.course_id ? ` · Khóa học #${job.course_id}` : ""}`,
          job.status === "FAILED" ? "alert error" : "muted",
        ),
      );
      if (job.status === "READY") {
        const download = button(
          "Tải CSV",
          () => {
            download.disabled = true;
            void api
              .download(
                `/exports/${job.id}/content`,
                `lms-${job.kind.toLowerCase()}-${job.id}.csv`,
              )
              .catch(actions.error)
              .finally(() => {
                download.disabled = false;
              });
          },
          "button secondary",
        );
        row.append(download);
      }
      if (job.status === "FAILED")
        row.append(
          element(
            "p",
            job.error_code === "ACCESS_REVOKED"
              ? "Quyền truy cập đã thay đổi. Liên hệ quản trị viên."
              : job.error_code === "ROW_LIMIT"
                ? "Dữ liệu vượt giới hạn 10.000 dòng. Hãy lọc hẹp hơn và tạo yêu cầu mới."
                : "Hãy thử tạo yêu cầu mới.",
            "muted",
          ),
        );
      list.append(row);
    }
    list.append(
      button(
        "Làm mới trạng thái xuất",
        () => {
          void load().catch(actions.error);
        },
        "button ghost",
      ),
      pagination(offset, page.limit, page.total, (n) => {
        offset = n;
        void load().catch(actions.error);
      }),
    );
    if (page.items.some((job) => job.status === "PENDING"))
      poll = window.setTimeout(() => {
        if (actions.current()) void load().catch(actions.error);
      }, 2000);
  };
  await load();
}

function reportTable(
  caption: string,
  columns: [string, string][],
  rows: Record<string, unknown>[],
) {
  const wrap = element("div", "", "table-scroll");
  const table = element("table", "", "report-table");
  table.append(element("caption", caption));
  const head = element("thead"),
    titles = element("tr");
  for (const [, label] of columns) {
    const th = element("th", label);
    th.scope = "col";
    titles.append(th);
  }
  head.append(titles);
  const content = element("tbody");
  for (const item of rows) {
    const row = element("tr");
    for (const [key] of columns)
      row.append(element("td", String(item[key] ?? "—")));
    content.append(row);
  }
  table.append(head, content);
  wrap.append(table);
  return wrap;
}

export async function renderCourseReports(
  body: HTMLElement,
  courseId: string,
  actions: PageActions,
) {
  const section = element("section", "", "panel course-reports");
  section.append(element("h2", "Báo cáo học tập"));
  let search = "",
    enrollmentStatus = "",
    gradeStatus = "PUBLISHED",
    assessmentType = "";
  let learnerOffset = 0,
    gradeOffset = 0,
    revision = 0;
  const lists = element("div");
  section.append(
    actionForm(
      [
        field("Tìm học viên trong báo cáo", "search", "search", false),
        selectField("Trạng thái ghi danh báo cáo", "enrollment_status", [
          ["", "Tất cả"],
          ["PENDING", "Chờ duyệt"],
          ["ACTIVE", "Đang học"],
          ["SUSPENDED", "Tạm ngưng"],
          ["COMPLETED", "Hoàn thành"],
        ]),
        selectField("Trạng thái điểm báo cáo", "grade_status", [
          ["PUBLISHED", "Đã công bố"],
          ["DRAFT", "Điểm nháp"],
          ["ALL", "Tất cả điểm"],
        ]),
        selectField("Loại đánh giá báo cáo", "assessment_type", [
          ["", "Tất cả"],
          ["ASSIGNMENT", "Bài tập"],
          ["EXAM", "Bài thi"],
        ]),
      ],
      "Lọc báo cáo",
      async (data) => {
        search = String(data.get("search")).trim();
        enrollmentStatus = String(data.get("enrollment_status"));
        gradeStatus = String(data.get("grade_status"));
        assessmentType = String(data.get("assessment_type"));
        learnerOffset = gradeOffset = 0;
        await load();
      },
      actions.error,
    ),
  );
  section.append(lists);
  body.append(section);
  const learnerFilters = () => ({
    search,
    ...(enrollmentStatus ? { enrollment_status: enrollmentStatus } : {}),
  });
  const gradeFilters = () => ({
    search,
    grade_status: gradeStatus,
    ...(assessmentType ? { assessment_type: assessmentType } : {}),
  });
  const load = async () => {
    const serial = ++revision;
    lists.setAttribute("aria-busy", "true");
    try {
      const [learners, grades] = await Promise.all([
        api.request<{
          items: Record<string, unknown>[];
          total: number;
          totals: Record<string, number>;
          limit: number;
        }>(
          `/reports/courses/${courseId}/learners?${new URLSearchParams({ ...learnerFilters(), limit: "10", offset: String(learnerOffset) })}`,
        ),
        api.request<{
          items: Record<string, unknown>[];
          total: number;
          limit: number;
        }>(
          `/reports/courses/${courseId}/gradebook?${new URLSearchParams({ ...gradeFilters(), limit: "10", offset: String(gradeOffset) })}`,
        ),
      ]);
      if (!actions.current() || serial !== revision) return;
      lists.replaceChildren(
        statistics([
          ["Học viên phù hợp", learners.total],
          ["Đang học", Number(learners.totals.active_learners)],
          ["Đã hoàn thành", Number(learners.totals.completed_learners)],
          [
            "Tiến độ trung bình (%)",
            Math.round(Number(learners.totals.average_progress)),
          ],
        ]),
      );
      if (learners.items.length)
        lists.append(
          reportTable(
            "Tiến độ học viên",
            [
              ["username", "Học viên"],
              ["status", "Ghi danh"],
              ["progress_percent", "Tiến độ (%)"],
              ["published_grades", "Điểm đã công bố"],
              ["draft_grades", "Điểm nháp"],
            ],
            learners.items,
          ),
        );
      else lists.append(element("p", "Không có học viên phù hợp.", "empty"));
      lists.append(
        pagination(learnerOffset, learners.limit, learners.total, (n) => {
          learnerOffset = n;
          void load().catch(actions.error);
        }),
      );
      if (grades.items.length)
        lists.append(
          reportTable(
            "Gradebook theo bộ lọc",
            [
              ["username", "Học viên"],
              ["assessment_title", "Đánh giá"],
              ["assessment_type", "Loại"],
              ["score", "Điểm"],
              ["max_score", "Điểm tối đa"],
              ["status", "Trạng thái"],
            ],
            grades.items,
          ),
        );
      else lists.append(element("p", "Không có điểm phù hợp.", "empty"));
      lists.append(
        pagination(gradeOffset, grades.limit, grades.total, (n) => {
          gradeOffset = n;
          void load().catch(actions.error);
        }),
      );
    } finally {
      if (serial === revision) lists.removeAttribute("aria-busy");
    }
  };
  await load();
  await renderExports(section, actions, () => [
    {
      label: "Xuất tiến độ CSV",
      kind: "LEARNERS",
      course_id: courseId,
      filters: learnerFilters(),
    },
    {
      label: "Xuất gradebook CSV",
      kind: "GRADEBOOK",
      course_id: courseId,
      filters: gradeFilters(),
    },
  ]);
}
