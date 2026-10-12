import { api } from "../../../services/api/client";
import { element, field } from "../../../components/dom";
import {
  actionForm,
  pagination,
  selectField,
  type PageActions,
} from "../../../components/forms";

export async function renderSecurity(
  body: HTMLElement,
  query: URLSearchParams,
  actions: PageActions,
) {
  const offset = Math.max(0, Number(query.get("offset")) || 0);
  const type = query.get("event_type") ?? "";
  const params = new URLSearchParams({ limit: "20", offset: String(offset) });
  if (type) params.set("event_type", type);
  const page = await api.request<{
    items: Record<string, unknown>[];
    total: number;
  }>(`/audit/security-events?${params}`);
  if (!actions.current()) return;
  body.append(
    actionForm(
      [
        selectField(
          "Loại sự kiện",
          "event_type",
          [
            ["", "Tất cả"],
            ...[
              "LOGIN_SUCCEEDED",
              "LOGIN_FAILED",
              "ACCESS_DENIED",
              "ACCOUNT_LOCKED",
              "TOKEN_REVOKED",
              "TOKEN_REUSE_DETECTED",
            ].map((s): [string, string] => [s, s]),
          ],
          type,
        ),
      ],
      "Lọc sự kiện",
      async (data) =>
        actions.navigate(
          `/admin/security?event_type=${data.get("event_type")}`,
        ),
      actions.error,
    ),
  );
  if (!page.items.length)
    body.append(element("p", "Không có sự kiện phù hợp.", "empty"));
  for (const row of page.items) {
    const card = element("article", "", "panel");
    card.append(
      element("h2", String(row.event_type)),
      element(
        "p",
        `${row.severity} · Người thực hiện #${row.actor_id ?? "Chưa xác thực"} · ${row.ip_address ?? ""}`,
      ),
      element(
        "p",
        `${new Date(String(row.created_at)).toLocaleString("vi-VN")} · Trace ID: ${row.trace_id}`,
        "muted",
      ),
      element("pre", JSON.stringify(row.details, null, 2), "lesson-text"),
    );
    body.append(card);
  }
  body.append(
    pagination(offset, 20, page.total, (n) =>
      actions.navigate(
        `/admin/security?${new URLSearchParams({ event_type: type, offset: String(n) })}`,
      ),
    ),
  );
}

interface AttemptEvent {
  id: string;
  attempt_id: string;
  student_id: string;
  exam_title: string;
  event_type: string;
  created_at: string;
  review_status: string;
  version: number;
  review_note: string | null;
}

export async function renderAttemptReview(
  body: HTMLElement,
  courseId: string,
  actions: PageActions,
) {
  const section = element("section", "", "panel attempt-review");
  section.append(
    element("h2", "Sự kiện bài thi"),
    element(
      "p",
      "Đổi tab hoặc mất focus tạo cờ cần xem xét. Giảng viên đánh giá ngữ cảnh; sự kiện không tự thay đổi điểm.",
      "muted",
    ),
  );
  const list = element("div");
  section.append(list);
  body.append(section);
  let offset = 0;
  const load = async () => {
    const page = await api.request<{
      items: AttemptEvent[];
      total: number;
      limit: number;
    }>(`/courses/${courseId}/attempt-events?limit=20&offset=${offset}`);
    if (!actions.current()) return;
    list.replaceChildren();
    if (!page.items.length)
      list.append(element("p", "Chưa ghi nhận sự kiện bài thi.", "empty"));
    for (const item of page.items) {
      const card = element("article", "", "panel");
      card.append(
        element("h3", `${item.exam_title} · Lượt thi #${item.attempt_id}`),
        element(
          "p",
          `Học viên #${item.student_id} · ${item.event_type} · ${item.review_status}`,
        ),
        element(
          "p",
          new Date(item.created_at).toLocaleString("vi-VN"),
          "muted",
        ),
      );
      if (item.review_status === "PENDING")
        card.append(
          actionForm(
            [
              selectField("Kết quả xem xét", "status", [
                ["REVIEWED", "Đã xem xét"],
                ["DISMISSED", "Bỏ qua dấu hiệu"],
              ]),
              field("Ghi chú xem xét", "note"),
            ],
            "Lưu xem xét",
            async (data) => {
              await api.request(
                `/courses/${courseId}/attempt-events/${item.id}/review`,
                "PATCH",
                {
                  expected_version: item.version,
                  status: data.get("status"),
                  note: data.get("note"),
                },
              );
              await load();
            },
            actions.error,
          ),
        );
      else if (item.review_note) card.append(element("p", item.review_note));
      list.append(card);
    }
    list.append(
      pagination(offset, page.limit, page.total, (n) => {
        offset = n;
        void load().catch(actions.error);
      }),
    );
  };
  await load();
}
