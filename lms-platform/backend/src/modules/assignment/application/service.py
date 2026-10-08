"""Course scope, assignment transitions and serialized submission attempts."""

from fastapi import HTTPException

from src.modules.assignment.domain.policy import submission_status
from src.modules.assignment.infrastructure.repository import AssignmentRepository
from src.modules.audit_security.infrastructure.repository import AuditRepository
from src.modules.course.application.service import CourseService
from src.modules.learning_progress_analytics.application.service import ProgressService
from src.modules.notification.application.events import NotificationEvents


class AssignmentService(CourseService):
    def __init__(self, connection, user, trace_id):
        super().__init__(connection, user, trace_id)
        self.assignments = AssignmentRepository(connection)

    async def is_manager(self, course):
        if "ADMIN" in self.user.roles or course["created_by"] == int(self.user.id):
            return True
        if "INSTRUCTOR" not in self.user.roles:
            return False
        row = await self.assignments.fetch_one(
            """SELECT id FROM course_staff WHERE course_id=:course AND user_id=:user
               AND role='INSTRUCTOR'""",
            {"course": course["id"], "user": int(self.user.id)},
        )
        return row is not None

    async def manager_assignment(self, course_id, assignment_id, *, write=False):
        course = await self.authorize(course_id, write=write)

        if not await self.is_manager(course):
            raise HTTPException(403)

        if write and course["status"] == "ARCHIVED":
            raise HTTPException(
            409,
            "Archived course cannot be edited",
        )

        assignment = await self.assignments.assignment(
        course_id,
        assignment_id,
        lock=write,
        )

        if assignment is None:
            raise HTTPException(404)

        return assignment

    async def student_assignment(self, course_id, assignment_id, *, write=False):
        # Lock the course before enrollment and assignment on writes. Locking reads
        # avoid a stale REPEATABLE READ snapshot after waiting for a state change.
        course = await self.assignments.fetch_one(
            "SELECT id, status FROM courses WHERE id=:id AND deleted_at IS NULL"
            + (" FOR UPDATE" if write else ""),
            {"id": course_id},
        )
        if course is None:
            raise HTTPException(404)
        if course["status"] != "PUBLISHED":
            raise HTTPException(403)
        enrollment = await self.assignments.fetch_one(
            """SELECT id, student_id FROM enrollments WHERE course_id=:course
               AND student_id=:student AND status='ACTIVE'"""
            + (" FOR UPDATE" if write else ""),
            {"course": course_id, "student": int(self.user.id)},
        )
        if enrollment is None:
            raise HTTPException(403)
        assignment = await self.assignments.assignment(course_id, assignment_id, lock=write)
        if assignment is None or assignment["status"] == "DRAFT":
            raise HTTPException(404)
        return assignment, enrollment

    async def submit(self, course_id, assignment_id, *, answer_text=None, file=None):
        assignment, enrollment = await self.student_assignment(course_id, assignment_id, write=True)
        now = (await self.assignments.fetch_one("SELECT UTC_TIMESTAMP(6) AS now"))["now"]
        status = submission_status(assignment, now)
        row = await self.assignments.fetch_one(
            """SELECT COALESCE(MAX(version), 0) AS version FROM assignment_submissions
               WHERE assignment_id=:assignment AND enrollment_id=:enrollment""",
            {"assignment": assignment_id, "enrollment": enrollment["id"]},
        )
        version = int(row["version"]) + 1
        if version > assignment["max_attempts"]:
            raise HTTPException(409, "Maximum submission attempts reached")
        if file is not None:
            if file["mime_type"] not in assignment["allowed_mime_types"].split(","):
                raise HTTPException(422, "File MIME is not allowed for this assignment")
            if file["size_bytes"] > assignment["max_file_bytes"]:
                raise HTTPException(413, "File exceeds assignment size limit")
        submission_id = await self.assignments.insert(
            """INSERT INTO assignment_submissions
               (assignment_id, enrollment_id, version, status, answer_text,
                submitted_at, submitted_by)
               VALUES (:assignment, :enrollment, :version, :status, :answer,
                       :now, :student)""",
            {
                "assignment": assignment_id,
                "enrollment": enrollment["id"],
                "version": version,
                "status": status,
                "answer": answer_text,
                "now": now,
                "student": int(self.user.id),
            },
        )
        if file is not None:
            await self.assignments.execute(
                """INSERT INTO submission_files
                   (submission_id, title, location, mime_type, size_bytes, sha256)
                   VALUES (:submission, :title, :location, :mime_type, :size_bytes, :sha256)""",
                {**file, "submission": submission_id},
            )
        await ProgressService(self.connection, self.user, self.trace_id).refresh_course(
            course_id, enrollment["id"]
        )
        await AuditRepository(self.connection).append_log(
            actor_id=int(self.user.id),
            action="assignment.submit",
            resource="assignment_submission",
            resource_id=str(submission_id),
            trace_id=self.trace_id,
            details={"assignment_id": str(assignment_id), "version": version, "status": status},
        )
        await NotificationEvents(self.connection).assignment_submitted(
            course_id,
            int(self.user.id),
            {"id": assignment_id, "title": assignment["title"]},
        )
        await self.connection.commit()
        return {
            "id": submission_id,
            "assignment_id": assignment_id,
            "enrollment_id": enrollment["id"],
            "version": version,
            "status": status,
            "answer_text": answer_text,
            "submitted_at": now,
            "submitted_by": int(self.user.id),
            "student_id": int(self.user.id),
        }
