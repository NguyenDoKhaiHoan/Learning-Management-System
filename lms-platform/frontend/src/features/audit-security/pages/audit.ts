import { api } from "../../../services/api/client";
import { element, field } from "../../../components/dom";
import {
  actionForm,
  pagination,
  prefill,
  type PageActions,
} from "../../../components/forms";

export async function renderAudit(
  body: HTMLElement,
  query: URLSearchParams,
  actions: PageActions,
) {
  const offset = Math.max(0, Number(query.get("offset")) || 0);
  const filters = new URLSearchParams({ limit: "20", offset: String(offset) });
  for (const key of ["action", "actor_id", "resource_id", "trace_id"])
    if (query.get(key)) filters.set(key, query.get(key)!);
  const page = await api.request<{
    items: Record<string, unknown>[];
    total: number;
  }>(`/audit/logs?${filters}`);
  if (!actions.current()) return;
  body.append(
    actionForm(
      [
        prefill(
          field("Hành động", "action", "text", false),
          query.get("action") ?? "",
        ),
        prefill(
          field("Mã người thực hiện", "actor_id", "number", false),
          query.get("actor_id") ?? "",
        ),
        prefill(
          field("Mã tài nguyên", "resource_id", "text", false),
          query.get("resource_id") ?? "",
        ),
        prefill(
          field("Trace ID", "trace_id", "text", false),
          query.get("trace_id") ?? "",
        ),
      ],
      "Lọc nhật ký",
      async (data) => {
        const next = new URLSearchParams();
        for (const [key, value] of data)
          if (String(value).trim()) next.set(key, String(value).trim());
        actions.navigate(`/admin/audit?${next}`);
      },
      actions.error,
    ),
  );
  if (!page.items.length)
    body.append(element("p", "Không có nhật ký phù hợp.", "empty"));
  for (const row of page.items) {
    const card = element("article", "", "panel");
    card.append(
      element("h2", String(row.action)),
      element(
        "p",
        `Người thực hiện #${row.actor_id ?? "Hệ thống"} · ${row.resource} #${row.resource_id ?? ""}`,
      ),
      element(
        "p",
        `${new Date(String(row.timestamp)).toLocaleString("vi-VN")} · Trace ID: ${row.trace_id}`,
        "muted",
      ),
      element("pre", JSON.stringify(row.details, null, 2), "lesson-text"),
    );
    body.append(card);
  }
  body.append(
    pagination(offset, 20, page.total, (n) => {
      filters.delete("limit");
      filters.set("offset", String(n));
      actions.navigate(`/admin/audit?${filters}`);
    }),
  );
}
