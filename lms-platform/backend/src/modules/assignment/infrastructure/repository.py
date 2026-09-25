"""SQL-only assignment and submission storage."""

from src.core.database.sql import SqlRepository


class AssignmentRepository(SqlRepository):
    async def assignment(self, course_id, assignment_id, *, lock=False):
        return await self.fetch_one(
            """SELECT a.id, a.course_id, a.title, a.description, a.status, a.opens_at,
                      a.due_at, a.allow_late, a.late_until, a.max_attempts,
                      a.max_file_bytes, a.allowed_mime_types, a.max_score, a.created_by,
                      a.created_at, a.updated_at
               FROM assignments a WHERE a.id=:assignment AND a.course_id=:course
                 AND a.deleted_at IS NULL"""
            + (" FOR UPDATE" if lock else ""),
            {"assignment": assignment_id, "course": course_id},
        )

    async def submission(self, assignment_id, submission_id):
        return await self.fetch_one(
            """SELECT s.id, s.assignment_id, s.enrollment_id, s.version, s.status,
                      s.answer_text, s.submitted_at, s.submitted_by,
                      e.student_id
               FROM assignment_submissions s JOIN enrollments e ON e.id=s.enrollment_id
               WHERE s.id=:submission AND s.assignment_id=:assignment""",
            {"submission": submission_id, "assignment": assignment_id},
        )

    async def submission_files(self, submission_id):
        return await self.fetch_all(
            """SELECT id, submission_id, title, mime_type, size_bytes, sha256, created_at
               FROM submission_files WHERE submission_id=:submission ORDER BY id""",
            {"submission": submission_id},
        )
