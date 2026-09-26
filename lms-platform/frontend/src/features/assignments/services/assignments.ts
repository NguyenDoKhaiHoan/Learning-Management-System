import type {
  Assignment,
  AssignmentInput,
  AssignmentStatus,
  AssignmentSubmission,
  SubmissionFile,
} from "../../../../../shared/contracts/api";

import { api } from "../../../services/api/client";

function base(courseId: string) {
  return `/courses/${courseId}` + `/assignments`;
}

export const assignmentsApi = {
  list(courseId: string) {
    return api.request<Assignment[]>(base(courseId));
  },

  create(courseId: string, body: AssignmentInput) {
    return api.request<Assignment>(base(courseId), "POST", body);
  },

  update(courseId: string, assignmentId: string, body: AssignmentInput) {
    return api.request<Assignment>(
      `${base(courseId)}/${assignmentId}`,
      "PUT",
      body,
    );
  },

  transition(
    courseId: string,
    assignmentId: string,
    status: Exclude<AssignmentStatus, "DRAFT">,
  ) {
    return api.request<Assignment>(
      `${base(courseId)}/${assignmentId}/status`,
      "POST",
      {
        status,
      },
    );
  },

  remove(courseId: string, assignmentId: string) {
    return api.request(`${base(courseId)}/${assignmentId}`, "DELETE");
  },

  submitText(courseId: string, assignmentId: string, answerText: string) {
    return api.request<AssignmentSubmission>(
      `${base(courseId)}/${assignmentId}/submissions`,
      "POST",
      {
        answer_text: answerText,
      },
    );
  },

  submitFile(courseId: string, assignmentId: string, file: File) {
    return api.upload<AssignmentSubmission>(
      `${base(courseId)}/${assignmentId}/submissions/file`,
      file,
    );
  },

  mine(courseId: string, assignmentId: string) {
    return api.request<AssignmentSubmission[]>(
      `${base(courseId)}/${assignmentId}/submissions/mine`,
    );
  },

  submissions(courseId: string, assignmentId: string) {
    return api.request<AssignmentSubmission[]>(
      `${base(courseId)}/${assignmentId}/submissions`,
    );
  },

  files(courseId: string, assignmentId: string, submissionId: string) {
    return api.request<SubmissionFile[]>(
      `${base(courseId)}` +
        `/${assignmentId}` +
        `/submissions/${submissionId}` +
        `/files`,
    );
  },

  downloadFile(
    courseId: string,
    assignmentId: string,
    submissionId: string,
    file: SubmissionFile,
  ) {
    return api.download(
      `${base(courseId)}` +
        `/${assignmentId}` +
        `/submissions/${submissionId}` +
        `/files/${file.id}/content`,

      file.title,
    );
  },
};
