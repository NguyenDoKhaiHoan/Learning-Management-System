import type { LessonResource } from "../../../../../shared/contracts/api";

import { api } from "../../../services/api/client";

function base(courseId: string, moduleId: string, lessonId: string) {
  return (
    `/courses/${courseId}` +
    `/modules/${moduleId}` +
    `/lessons/${lessonId}` +
    `/resources`
  );
}

export const resourcesApi = {
  list(courseId: string, moduleId: string, lessonId: string) {
    return api.request<LessonResource[]>(base(courseId, moduleId, lessonId));
  },

  createLink(
    courseId: string,
    moduleId: string,
    lessonId: string,
    title: string,
    url: string,
  ) {
    return api.request<LessonResource>(
      base(courseId, moduleId, lessonId),

      "POST",

      {
        title,
        url,
      },
    );
  },

  upload(courseId: string, moduleId: string, lessonId: string, file: File) {
    return api.upload<LessonResource>(
      base(courseId, moduleId, lessonId) + "/file",

      file,
    );
  },

  remove(
    courseId: string,
    moduleId: string,
    lessonId: string,
    resourceId: string,
  ) {
    return api.request<{
      id: string;
    }>(
      base(courseId, moduleId, lessonId) + `/${resourceId}`,

      "DELETE",
    );
  },

  download(
    courseId: string,
    moduleId: string,
    lessonId: string,
    resource: LessonResource,
  ) {
    return api.download(
      base(courseId, moduleId, lessonId) + `/${resource.id}/content`,

      resource.title,
    );
  },
};
