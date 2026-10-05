"""Read-only dashboard summaries; each instructor query applies course ownership/staff scope."""

from src.core.database.sql import SqlRepository


class DashboardReports(SqlRepository):
    async def courses(self, actor, admin=False):
        return await self.fetch_all(
            """SELECT c.id,c.code,c.title,c.status,
            (SELECT COUNT(*) FROM enrollments e WHERE e.course_id=c.id) AS enrollments,
            (SELECT COUNT(*) FROM enrollments e WHERE e.course_id=c.id
                AND e.status='ACTIVE') AS active_enrollments,
            (SELECT COUNT(*) FROM enrollments e JOIN course_progress p ON p.enrollment_id=e.id
                WHERE e.course_id=c.id AND p.completed_at IS NOT NULL) AS completed_learners,
            (SELECT COUNT(*) FROM gradebook_entries g JOIN enrollments e ON e.id=g.enrollment_id
                WHERE e.course_id=c.id AND g.status='DRAFT') AS draft_grades,
            (SELECT COUNT(*) FROM assignment_submissions s
                JOIN assignments a ON a.id=s.assignment_id WHERE a.course_id=c.id
                AND a.deleted_at IS NULL) AS submissions
            FROM courses c WHERE c.deleted_at IS NULL AND (:admin=1 OR c.created_by=:user
                OR EXISTS (SELECT 1 FROM course_staff s WHERE s.course_id=c.id
                AND s.user_id=:user AND s.role='INSTRUCTOR')) ORDER BY c.id DESC""",
            {"admin": admin, "user": int(actor.id)},
        )

    async def overview(self, actor):
        users = await self.fetch_one("""SELECT COUNT(*) AS total_users,
            COALESCE(SUM(status='ACTIVE'),0) AS active_users FROM users WHERE deleted_at IS NULL""")
        courses = await self.courses(actor, admin=True)
        totals = {
            "total_courses": len(courses),
            "published_courses": sum(c["status"] == "PUBLISHED" for c in courses),
            "enrollments": sum(c["enrollments"] for c in courses),
            "active_enrollments": sum(c["active_enrollments"] for c in courses),
            "completed_learners": sum(c["completed_learners"] for c in courses),
        }
        return {"totals": users | totals, "courses": courses}
