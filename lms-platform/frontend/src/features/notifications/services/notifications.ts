import type { NotificationPage } from "../../../../../shared/contracts/api";
import { api } from "../../../services/api/client";

export const notificationsApi = {
  list(limit = 20, offset = 0, unreadOnly = false) {
    return api.request<NotificationPage>(
      `/notifications?limit=${limit}&offset=${offset}&unread_only=${unreadOnly}`,
    );
  },
  markRead(id: string) {
    return api.request(`/notifications/${id}/read`, "PATCH");
  },
  markAllRead() {
    return api.request("/notifications/read-all", "POST");
  },
  unreadCount() {
    return api.request<{ unread: number }>("/notifications/unread-count");
  },
};
