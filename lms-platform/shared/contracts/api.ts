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

export interface AdminUser {
  id: string;
  email: string;
  username: string;
  status: "ACTIVE" | "INACTIVE" | "LOCKED";
  roles: string[];
  created_at: string;
  updated_at: string;
}
export interface UserPage {
  items: AdminUser[];
  total: number;
  limit: number;
  offset: number;
}
export interface CourseReport {
  id: string;
  code: string;
  title: string;
  status: CourseStatus;
  enrollments: number;
  active_enrollments: number;
  completed_learners: number;
  draft_grades: number;
  submissions: number;
}
export interface DashboardReport {
  totals: Record<string, number>;
  courses: CourseReport[];
  total_courses: number;
  limit: number;
  offset: number;
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
export interface ContentOrder {
  ids: string[];
}

export type EnrollmentStatus = "PENDING" | "ACTIVE" | "SUSPENDED" | "COMPLETED";
export interface Enrollment {
  id: string;
  student_id: string;
  course_id: string;
  status: EnrollmentStatus;
  completed_at: string | null;
}
export interface MyEnrollment extends Enrollment {
  title: string;
  course_status: CourseStatus;
}
export interface CourseStaff {
  user_id: string;
  username: string;
  role: "INSTRUCTOR" | "ASSISTANT";
}
export type CatalogCourse = Pick<
  Course,
  "id" | "code" | "title" | "description"
>;

export type LessonResourceType = "LINK" | "FILE";

export interface LessonResource {
  id: string;
  lesson_id: string;
  title: string;

  resource_type: LessonResourceType;

  url?: string | null;

  mime_type?: string | null;
  size_bytes?: number | null;
  sha256?: string | null;
  uploaded_by?: string | null;
}

export type LessonProgressStatus = "NOT_STARTED" | "IN_PROGRESS" | "COMPLETED";

export interface CompletionRule {
  course_id: string;

  required_lesson_percent: number;

  require_submitted_assignments: boolean;
  require_published_assignment_grades: boolean;
  require_published_exam_grades: boolean;
  minimum_grade_percent: number;

  updated_by: string | null;
  updated_at: string | null;
}

export interface CourseProgress {
  enrollment_id: string;

  completed_lessons: number;
  total_lessons: number;

  completed_assignments: number;
  total_assignments: number;
  passed_assignments: number;
  total_exams: number;
  passed_exams: number;

  progress_percent: number;

  completed_at: string | null;
  updated_at: string | null;
}

export interface ProgressUpdate {
  lesson: {
    enrollment_id: string;
    lesson_id: string;

    status: LessonProgressStatus;

    last_position_seconds: number;

    started_at: string;

    completed_at: string | null;

    updated_at: string;
  };

  course: CourseProgress;
}

export type AssignmentStatus = "DRAFT" | "PUBLISHED" | "CLOSED" | "ARCHIVED";

export interface AssignmentInput {
  title: string;

  description: string;

  opens_at: string;
  due_at: string;

  allow_late: boolean;

  late_until: string | null;

  max_attempts: number;

  max_file_bytes: number;

  allowed_mime_types: string[];

  max_score: number;
}

export interface Assignment extends AssignmentInput {
  id: string;

  course_id: string;

  status: AssignmentStatus;

  created_by: string;
}

export interface AssignmentSubmission {
  id: string;

  assignment_id: string;

  enrollment_id: string;

  version: number;

  status: "SUBMITTED" | "LATE";

  answer_text: string | null;

  submitted_at: string;

  submitted_by: string;

  student_id: string;
}

export interface SubmissionFile {
  id: string;

  submission_id: string;

  title: string;

  mime_type: string;

  size_bytes: number;

  sha256: string;

  created_at: string;
}
