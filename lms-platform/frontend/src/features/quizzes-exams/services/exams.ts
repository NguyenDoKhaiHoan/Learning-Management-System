import type { ExamAttemptView, ExamEligibility, ExamSummary } from "../../../../../shared/contracts/api";
import { api } from "../../../services/api/client";

export const examsApi = {
  list(courseId: string) {
    return api.request<ExamSummary[]>(`/courses/${courseId}/exams`);
  },
  eligibility(examId: string) {
    return api.request<ExamEligibility>(`/exams/${examId}/eligibility`);
  },
  start(examId: string) {
    return api.request<ExamAttemptView>(`/exams/${examId}/attempts`, "POST");
  },
  resume(attemptId: string) {
    return api.request<ExamAttemptView>(`/attempts/${attemptId}`);
  },
  save(attemptId: string, questionId: number, selectedOptionIds: number[], expectedVersion: number) {
    return api.request<{ id: string; server_version: number }>(
      `/attempts/${attemptId}/answers/${questionId}`,
      "PUT",
      { selected_option_ids: selectedOptionIds, expected_version: expectedVersion },
    );
  },
  submit(attemptId: string) {
    return api.request<ExamAttemptView>(`/attempts/${attemptId}/submit`, "POST");
  },
};
