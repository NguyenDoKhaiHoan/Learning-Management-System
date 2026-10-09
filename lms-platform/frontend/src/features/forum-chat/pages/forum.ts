import type { ForumThread, ForumThreadDetail } from "../../../../../shared/contracts/api";
import { button, element } from "../../../components/dom";
import { actionForm, type PageActions } from "../../../components/forms";
import { forumApi } from "../services/forum";

function textField(label: string, name: string, multiline = false) {
  const wrap = element("label", label, "field");
  const input = multiline ? document.createElement("textarea") : document.createElement("input");
  input.name = name;
  input.required = true;
  if (multiline) (input as HTMLTextAreaElement).rows = 4;
  wrap.append(input);
  return wrap;
}

function date(value: string) {
  return new Intl.DateTimeFormat("vi-VN", { dateStyle: "medium", timeStyle: "short" }).format(new Date(value));
}

function row(thread: ForumThread, open: () => void) {
  const item = element("article", "", "forum-thread panel");
  const link = button(thread.title, open, "link-button");
  link.setAttribute("aria-label", `Mở thảo luận ${thread.title}`);
  item.append(link, element("p", thread.body, "forum-excerpt"), element("small", `${thread.author_username} · ${date(thread.updated_at)} · ${thread.reply_count} phản hồi`, "muted"));
  return item;
}

function detail(detail: ForumThreadDetail, courseId: string, actions: PageActions) {
  const section = element("section", "", "forum-detail");
  section.append(button("← Danh sách thảo luận", () => void actions.navigate(`/courses/${courseId}`), "button ghost"));
  section.append(element("h3", detail.title), element("p", detail.body, "forum-body"), element("p", `${detail.author_username} · ${date(detail.created_at)}`, "muted"));
  const replies = element("div", "", "forum-replies");
  replies.append(element("h4", `Phản hồi (${detail.messages.length})`));
  if (!detail.messages.length) replies.append(element("p", "Chưa có phản hồi.", "empty"));
  for (const message of detail.messages) {
    const reply = element("article", "", "forum-reply panel");
    reply.append(element("p", message.body), element("small", `${message.author_username} · ${date(message.created_at)}`, "muted"));
    replies.append(reply);
  }
  replies.append(actionForm([textField("Viết phản hồi", "body", true)], "Gửi phản hồi", async (data) => {
    await forumApi.reply(courseId, detail.id, String(data.get("body")));
    actions.navigate(`/courses/${courseId}`);
  }, actions.error));
  section.append(replies);
  return section;
}

export async function renderForum(target: HTMLElement, courseId: string, actions: PageActions) {
  const section = element("section", "", "forum-page");
  section.append(element("h2", "Thảo luận khóa học"), element("p", "Đặt câu hỏi và chia sẻ kinh nghiệm với lớp học.", "muted"));
  await forumApi.forum(courseId);
  const page = await forumApi.threads(courseId);
  section.append(actionForm([textField("Tiêu đề thảo luận", "title"), textField("Nội dung", "body", true)], "Tạo thảo luận", async (data) => {
    await forumApi.createThread(courseId, String(data.get("title")), String(data.get("body")));
    actions.navigate(`/courses/${courseId}`);
  }, actions.error));
  const list = element("div", "", "forum-list");
  if (!page.items.length) list.append(element("p", "Chưa có thảo luận. Hãy mở đầu cuộc trao đổi.", "empty"));
  for (const thread of page.items) list.append(row(thread, async () => {
    try { section.replaceChildren(detail(await forumApi.thread(courseId, thread.id), courseId, actions)); }
    catch (error) { actions.error(error); }
  }));
  section.append(list);
  target.append(section);
}
