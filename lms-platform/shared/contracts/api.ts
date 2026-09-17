/** API v1 transport types. BIGINT IDs are strings; roles always come from the server. */
export interface ErrorDetail {
  location: (string | number)[];
  type: string;
  message: string;
}
export interface ApiError {
  code: string;
  message: string;
  details: ErrorDetail[];
  trace_id: string;
}
export interface ApiSuccess<T> {
  code: string;
  message: string;
  data: T;
  trace_id: string;
}
export interface CurrentUser {
  id: string;
  email: string;
  username: string;
  roles: string[];
}

export interface AccessToken {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
  refresh_expires_in: number;
}
export type CourseStatus = "DRAFT" | "PUBLISHED" | "ARCHIVED";
export interface CourseInput {
  code: string;
  title: string;
  description?: string | null;
}
export interface Course extends CourseInput {
  id: string;
  created_by: string;
  status: CourseStatus;
  created_at: string;
  updated_at: string;
}
export interface LessonInput {
  title: string;
  lesson_type: "VIDEO" | "ARTICLE" | "DOCUMENT" | "LIVE";
  is_preview?: boolean;
  content?: string | null;
}
export interface Lesson extends LessonInput {
  id: string;
  position: number;
  is_preview: boolean;
  content: string | null;
}
export interface CourseModule {
  id: string;
  title: string;
  position: number;
  lessons: Lesson[];
}
// Send IDs as decimal strings to preserve BIGINT precision; API accepts them.
export interface ContentOrder { ids: string[]; }
