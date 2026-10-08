"""Public event handlers. Notifications commit atomically with the business write."""

from src.modules.notification.infrastructure.repository import NotificationRepository


class NotificationEvents:
    def __init__(self, connection):
        self.repo = NotificationRepository(connection)

    async def course_managers(self, course_id, type, title, body, resource_type, resource_id):
        recipients = await self.repo.fetch_all(
            """SELECT u.id FROM users u WHERE u.deleted_at IS NULL AND u.status='ACTIVE'
            AND (u.id=(SELECT created_by FROM courses WHERE id=:course)
                OR EXISTS (SELECT 1 FROM course_staff s WHERE s.course_id=:course
                           AND s.user_id=u.id AND s.role='INSTRUCTOR'))""",
            {"course": course_id},
        )
        for recipient in recipients:
            await self.repo.create(
                recipient_id=recipient["id"], course_id=course_id, type=type,
                title=title, body=body, resource_type=resource_type, resource_id=resource_id,
            )

    async def enrollment_requested(self, course_id, student_id):
        await self.course_managers(
            course_id, "ENROLLMENT_REQUEST", "Yêu cầu ghi danh mới",
            f"Học viên #{student_id} muốn tham gia khóa học.", "course", course_id,
        )

    async def enrollment_changed(self, course_id, student_id, status, title):
        label = "đã được kích hoạt" if status == "ACTIVE" else "đã bị tạm ngưng"
        await self.repo.create(
            recipient_id=student_id, course_id=course_id, type="ENROLLMENT_STATUS",
            title="Trạng thái ghi danh đã thay đổi", body=f"Ghi danh {title} {label}.",
            resource_type="course", resource_id=course_id,
        )

    async def assignment_submitted(self, course_id, student_id, assignment):
        await self.course_managers(
            course_id, "ASSIGNMENT_SUBMITTED", "Bài nộp mới",
            f"Học viên #{student_id} đã nộp {assignment['title']}.",
            "assignment", assignment["id"],
        )

    async def grade_published(self, course_id, enrollment_id, grade_id):
        recipient = await self.repo.fetch_one(
            "SELECT student_id FROM enrollments WHERE id=:id", {"id": enrollment_id}
        )
        await self.repo.create(
            recipient_id=recipient["student_id"], course_id=course_id,
            type="GRADE_PUBLISHED", title="Điểm đã được công bố",
            body="Bạn có kết quả mới. Mở khóa học để xem điểm và nhận xét.",
            resource_type="grade", resource_id=grade_id,
        )
