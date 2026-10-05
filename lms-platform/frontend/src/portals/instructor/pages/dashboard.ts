import type { DashboardReport } from "../../../../../shared/contracts/api";
import { api } from "../../../services/api/client";
import { element } from "../../../components/dom";
import { statistics, type PageActions } from "../../../components/forms";

export async function renderInstructorSummary(
  body: HTMLElement,
  actions: PageActions,
) {
  const report = await api.request<DashboardReport>(
    "/dashboard/instructor?limit=100",
  );
  if (!actions.current()) return;
  const t = report.totals;
  body.append(
    element("h2", "Tổng quan giảng dạy"),
    statistics([
      ["Lớp phụ trách", t.total_courses],
      ["Học viên đang học", t.active_enrollments],
      ["Bài đã nộp", t.submissions],
      ["Điểm chờ công bố", t.draft_grades],
    ]),
  );
}
