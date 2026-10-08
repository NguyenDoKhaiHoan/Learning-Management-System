import type { GradeView } from "../../../../../shared/contracts/api";
import { api } from "../../../services/api/client";

export const gradesApi = {
  mine(courseId: string) {
    return api.request<GradeView[]>(`/courses/${courseId}/grades/me`);
  },
};
