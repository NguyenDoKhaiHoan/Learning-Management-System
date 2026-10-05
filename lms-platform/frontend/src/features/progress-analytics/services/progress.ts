import type {
  CompletionRule,
  CourseProgress,
  LessonProgressStatus,
  ProgressUpdate,
} from "../../../../../shared/contracts/api";

import { api } from "../../../services/api/client";

export const progressApi = {
  rule(courseId: string) {
    return api.request<CompletionRule>(`/courses/${courseId}/completion-rule`);
  },

  updateRule(
    courseId: string,
    percent: number,
    assignments: boolean,
    grades: Pick<
      CompletionRule,
      | "require_published_assignment_grades"
      | "require_published_exam_grades"
      | "minimum_grade_percent"
    >,
  ) {
    return api.request<CompletionRule>(
      `/courses/${courseId}/completion-rule`,

      "PUT",

      {
        required_lesson_percent: percent,

        require_submitted_assignments: assignments,
        ...grades,
      },
    );
  },

  mine(courseId: string) {
    return api.request<CourseProgress>(`/courses/${courseId}/progress/me`);
  },

  updateLesson(
    courseId: string,
    lessonId: string,
    status: LessonProgressStatus,
    position = 0,
  ) {
    return api.request<ProgressUpdate>(
      `/courses/${courseId}/lessons/${lessonId}/progress`,

      "PUT",

      {
        status,

        last_position_seconds: position,
      },
    );
  },
};
