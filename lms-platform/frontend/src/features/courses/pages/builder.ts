import type { Course, CourseModule } from "../../../../../shared/contracts/api";
import { api } from "../../../services/api/client";
import { button, element, field } from "../../../components/dom";
import {
  actionForm,
  prefill,
  selectField,
  type PageActions,
} from "../../../components/forms";

function deleteControl(
  label: string,
  path: string,
  actions: PageActions,
  after?: () => void,
) {
  const box = element("details", "", "delete-control");
  box.append(
    element("summary", label),
    element("p", "Xác nhận xóa nội dung này khỏi khóa học?"),
    button(
      "Xác nhận " + label.toLowerCase(),
      () => {
        void actions.perform(async () => {
          await api.request(path, "DELETE");
          after?.();
        }, "Đã xóa nội dung.");
      },
      "button danger",
    ),
  );
  return box;
}

function reorderControls(
  ids: string[],
  id: string,
  path: string,
  actions: PageActions,
) {
  const group = element("div", "", "actions");
  const index = ids.indexOf(id);
  for (const [delta, label] of [
    [-1, "Đưa lên"],
    [1, "Đưa xuống"],
  ] as const) {
    const move = button(
      label,
      () => {
        const next = [...ids];
        [next[index], next[index + delta]] = [next[index + delta], next[index]];
        void actions.perform(
          () => api.request(path, "PUT", { ids: next }),
          "Đã sắp xếp nội dung.",
        );
      },
      "button secondary",
    );
    move.disabled = index + delta < 0 || index + delta >= ids.length;
    group.append(move);
  }
  return group;
}

export function courseSettings(
  course: Course,
  actions: PageActions,
  home: string,
) {
  const panel = element("details", "", "panel course-settings");
  panel.append(element("summary", "Thông tin & quản lý khóa học"));
  if (course.status === "DRAFT") {
    panel.append(
      actionForm(
        [
          prefill(field("Mã khóa học chỉnh sửa", "code"), course.code),
          prefill(field("Tên khóa học chỉnh sửa", "title"), course.title),
          prefill(
            field("Mô tả chỉnh sửa", "description", "text", false),
            course.description ?? "",
          ),
        ],
        "Lưu thông tin khóa học",
        (data) =>
          actions.perform(
            () =>
              api.request(
                `/courses/${course.id}`,
                "PUT",
                Object.fromEntries(data),
              ),
            "Đã lưu thông tin khóa học.",
          ),
        actions.error,
      ),
    );
    panel.append(
      deleteControl("Xóa khóa học", `/courses/${course.id}`, actions, () =>
        actions.navigate(home),
      ),
    );
  } else {
    panel.append(element("p", "Chuyển khóa học về bản nháp để sửa nội dung."));
  }
  if (course.status === "PUBLISHED")
    panel.append(
      button(
        "Lưu trữ khóa học",
        () => {
          void actions.perform(
            () =>
              api.request(`/courses/${course.id}/status`, "POST", {
                status: "ARCHIVED",
              }),
            "Đã lưu trữ khóa học.",
          );
        },
        "button secondary",
      ),
    );
  return panel;
}

export function moduleEditor(
  courseId: string,
  module: CourseModule,
  modules: CourseModule[],
  actions: PageActions,
) {
  const path = `/courses/${courseId}/modules/${module.id}`;
  const edit = element("details", "", "builder-edit");
  edit.append(
    element("summary", "Sửa chương"),
    actionForm(
      [prefill(field("Tên chương chỉnh sửa", "title"), module.title)],
      "Lưu chương",
      (data) =>
        actions.perform(
          () => api.request(path, "PUT", Object.fromEntries(data)),
          "Đã lưu chương.",
        ),
      actions.error,
    ),
  );
  edit.append(
    reorderControls(
      modules.map((m) => m.id),
      module.id,
      `/courses/${courseId}/modules/order`,
      actions,
    ),
    deleteControl("Xóa chương", path, actions),
  );
  return edit;
}

export function lessonEditor(
  courseId: string,
  module: CourseModule,
  lesson: CourseModule["lessons"][number],
  actions: PageActions,
) {
  const path = `/courses/${courseId}/modules/${module.id}/lessons/${lesson.id}`;
  const edit = element("details", "", "builder-edit");
  const content = element("label", "Nội dung chỉnh sửa", "field");
  const textarea = element("textarea");
  textarea.value = lesson.content ?? "";
  textarea.name = "content";
  textarea.rows = 5;
  content.append(textarea);
  const preview = prefill(
    field("Cho xem trước", "is_preview", "checkbox", false),
    lesson.is_preview,
  );
  edit.append(
    element("summary", "Sửa bài học"),
    actionForm(
      [
        prefill(field("Tên bài học chỉnh sửa", "title"), lesson.title),
        content,
        selectField(
          "Loại bài học",
          "lesson_type",
          [
            ["ARTICLE", "Bài đọc"],
            ["VIDEO", "Video"],
            ["DOCUMENT", "Tài liệu"],
            ["LIVE", "Trực tiếp"],
          ],
          lesson.lesson_type,
        ),
        preview,
      ],
      "Lưu nội dung bài học",
      (data) =>
        actions.perform(
          () =>
            api.request(path, "PUT", {
              title: data.get("title"),
              content: data.get("content"),
              lesson_type: data.get("lesson_type"),
              is_preview: data.get("is_preview") === "on",
            }),
          "Đã lưu nội dung bài học.",
        ),
      actions.error,
    ),
  );
  edit.append(
    reorderControls(
      module.lessons.map((l) => l.id),
      lesson.id,
      `/courses/${courseId}/modules/${module.id}/lessons/order`,
      actions,
    ),
    deleteControl("Xóa bài học", path, actions),
  );
  return edit;
}
