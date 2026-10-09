import type { Forum, ForumMessage, ForumThread, ForumThreadDetail, ForumThreadPage } from "../../../../../shared/contracts/api";
import { api } from "../../../services/api/client";

export const forumApi = {
  forum: (courseId: string) => api.request<Forum>(`/courses/${courseId}/forum`),
  threads: (courseId: string) => api.request<ForumThreadPage>(`/courses/${courseId}/forum/threads?limit=20&offset=0`),
  createThread: (courseId: string, title: string, body: string) => api.request<ForumThread>(`/courses/${courseId}/forum/threads`, "POST", { title, body }),
  thread: (courseId: string, threadId: string) => api.request<ForumThreadDetail>(`/courses/${courseId}/forum/threads/${threadId}`),
  reply: (courseId: string, threadId: string, body: string) => api.request<ForumMessage>(`/courses/${courseId}/forum/threads/${threadId}/messages`, "POST", { body }),
};
