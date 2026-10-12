"""Manager-scoped report projections; aggregates cover all filtered rows."""

from fastapi import HTTPException

from src.modules.course.application.service import CourseService

LEARNER_COLUMNS = [
    "enrollment_id",
    "student_id",
    "username",
    "status",
    "progress_percent",
    "completed_at",
    "published_grades",
    "draft_grades",
]
GRADE_COLUMNS = [
    "grade_id",
    "enrollment_id",
    "student_id",
    "username",
    "assessment_type",
    "assessment_id",
    "assessment_title",
    "score",
    "max_score",
    "status",
    "version",
    "published_at",
    "feedback",
]
OVERVIEW_COLUMNS = [
    "id",
    "code",
    "title",
    "status",
    "enrollments",
    "active_enrollments",
    "completed_learners",
    "draft_grades",
    "submissions",
]


def public_ids(rows):
    for row in rows:
        for key in ("enrollment_id", "student_id", "grade_id", "assessment_id"):
            if row.get(key) is not None:
                row[key] = str(row[key])
    return rows


class CourseReports(CourseService):
    async def scope(self, course_id):
        if not {"ADMIN", "INSTRUCTOR"}.intersection(self.user.roles):
            raise HTTPException(403)
        return await self.authorize(course_id, write=True)

    async def learners(self, course_id, filters, limit, offset):
        params = {
            "course": course_id,
            "status": filters.get("enrollment_status"),
            "search": filters.get("search", ""),
            "limit": limit,
            "offset": offset,
        }
        source = """FROM enrollments e JOIN users u ON u.id=e.student_id
            LEFT JOIN course_progress p ON p.enrollment_id=e.id
            WHERE e.course_id=:course AND u.deleted_at IS NULL
            AND (:status IS NULL OR e.status=:status)
            AND (:search='' OR LOCATE(:search,u.username)>0)"""
        totals = await self.repo.fetch_one(
            """SELECT COUNT(*) total_learners,COALESCE(SUM(e.status='ACTIVE'),0) active_learners,
            COALESCE(SUM(p.completed_at IS NOT NULL),0) completed_learners,
            COALESCE(AVG(COALESCE(p.progress_percent,0)),0) average_progress """
            + source
            + " FOR UPDATE",
            params,
        )
        for key in ("total_learners", "active_learners", "completed_learners"):
            totals[key] = int(totals[key])
        totals["average_progress"] = float(totals["average_progress"])
        rows = await self.repo.fetch_all(
            """SELECT e.id enrollment_id,e.student_id,u.username,e.status,
            COALESCE(p.progress_percent,0) progress_percent,p.completed_at,
            (SELECT COUNT(*) FROM gradebook_entries g WHERE g.enrollment_id=e.id
                AND g.status='PUBLISHED' FOR UPDATE) published_grades,
            (SELECT COUNT(*) FROM gradebook_entries g WHERE g.enrollment_id=e.id
                AND g.status='DRAFT' FOR UPDATE) draft_grades """
            + source
            + " ORDER BY e.id LIMIT :limit OFFSET :offset FOR UPDATE",
            params,
        )
        return {
            "items": public_ids(rows),
            "totals": totals,
            "total": totals["total_learners"],
            "limit": limit,
            "offset": offset,
        }

    async def gradebook(self, course_id, filters, limit, offset):
        params = {
            "course": course_id,
            "status": filters.get("grade_status", "PUBLISHED"),
            "type": filters.get("assessment_type"),
            "search": filters.get("search", ""),
            "limit": limit,
            "offset": offset,
        }
        source = """FROM gradebook_entries g JOIN enrollments e ON e.id=g.enrollment_id
            JOIN users u ON u.id=e.student_id
            LEFT JOIN assignments a ON g.assessment_type='ASSIGNMENT' AND a.id=g.assessment_id
            LEFT JOIN exams x ON g.assessment_type='EXAM' AND x.id=g.assessment_id
            WHERE e.course_id=:course AND u.deleted_at IS NULL
            AND (:status='ALL' OR g.status=:status) AND (:type IS NULL OR g.assessment_type=:type)
            AND (:search='' OR LOCATE(:search,u.username)>0)"""
        count = await self.repo.fetch_one("SELECT COUNT(*) total " + source + " FOR UPDATE", params)
        rows = await self.repo.fetch_all(
            """SELECT g.id grade_id,e.id enrollment_id,e.student_id,u.username,g.assessment_type,
            g.assessment_id,COALESCE(a.title,x.title) assessment_title,g.score,g.max_score,
            g.status,g.version,g.published_at,g.feedback """
            + source
            + " ORDER BY e.id,g.assessment_type,g.assessment_id,g.id "
            "LIMIT :limit OFFSET :offset FOR UPDATE",
            params,
        )
        return {
            "items": public_ids(rows),
            "total": count["total"],
            "limit": limit,
            "offset": offset,
        }
