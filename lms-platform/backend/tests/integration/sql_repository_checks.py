"""Exercise actual bound SQL and transaction behavior against disposable MySQL."""

import json
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine

from src.modules.audit_security.domain.enums import SecurityEventType
from src.modules.audit_security.infrastructure.repository import AuditRepository
from src.modules.course.domain.enums import CourseStatus
from src.modules.course.infrastructure.repository import CourseRepository
from src.modules.enrollment.domain.enums import CourseStaffRole, EnrollmentStatus
from src.modules.enrollment.infrastructure.repository import EnrollmentRepository
from src.modules.identity_access.domain.enums import UserStatus
from src.modules.identity_access.infrastructure.repository import IdentityRepository
from src.modules.learning_content.domain.enums import LessonType, ResourceType
from src.modules.learning_content.infrastructure.repository import ContentRepository
from src.modules.user_role.infrastructure.repository import RoleRepository


async def assert_sql_repositories(engine: AsyncEngine) -> None:
    async with engine.begin() as connection:
        identity = IdentityRepository(connection)
        roles = RoleRepository(connection)
        courses = CourseRepository(connection)
        content = ContentRepository(connection)
        enrollments = EnrollmentRepository(connection)
        audit = AuditRepository(connection)
        email = "student' OR 1=1 -- @example.com"
        user = await identity.create_user(
            email=email,
            username="sql_student",
            hashed_password="private-test-hash",
            status=UserStatus.ACTIVE,
        )
        assert (await identity.get_credentials(email))["id"] == user
        assert await identity.get_credentials("' OR 1=1 -- ") is None
        assert "hashed_password" not in await identity.get_user(user)
        role = await roles.create_role("STUDENT", "Student")
        permission = await roles.create_permission("course.read")
        await roles.assign_role(user, role)
        await roles.grant_permission(role, permission)
        assert await roles.get_role_codes(user) == ["STUDENT"]
        assert await roles.get_permission_codes(user) == ["course.read"]
        assert await identity.set_status(user, UserStatus.LOCKED)
        assert await roles.get_role_codes(user) == []
        assert await identity.set_status(user, UserStatus.ACTIVE)
        course = await courses.create(code="RAW_SQL", title="SQL thuần 🎓", created_by=user)
        assert (await courses.get(course))["status"] == "DRAFT"
        assert await courses.change_status(
            course, expected=CourseStatus.DRAFT, new=CourseStatus.PUBLISHED
        )
        assert not await courses.change_status(
            course, expected=CourseStatus.DRAFT, new=CourseStatus.ARCHIVED
        )
        assert (await courses.list_by_status(CourseStatus.PUBLISHED, limit=1))[0]["id"] == course
        with pytest.raises(ValueError):
            await courses.list_by_status(CourseStatus.PUBLISHED, limit=101)
        module = await content.create_module(course_id=course, title="Module SQL", position=1)
        lesson = await content.create_lesson(
            module_id=module, title="Lesson", position=1, lesson_type=LessonType.ARTICLE
        )
        resource = await content.add_resource(
            lesson_id=lesson,
            title="File",
            resource_type=ResourceType.FILE,
            location="private/example.pdf",
        )
        assert (await content.get_lesson(lesson))["course_id"] == course
        assert (await content.list_resources(lesson))[0]["id"] == resource
        enrollment = await enrollments.create(student_id=user, course_id=course)
        assert (await enrollments.get(student_id=user, course_id=course))["status"] == "PENDING"
        with pytest.raises(IntegrityError):
            async with connection.begin_nested():
                await enrollments.create(student_id=user, course_id=course)
        assert await enrollments.change_status(
            enrollment, expected=EnrollmentStatus.PENDING, new=EnrollmentStatus.ACTIVE
        )
        await enrollments.assign_staff(
            course_id=course, user_id=user, role=CourseStaffRole.INSTRUCTOR
        )
        expires = datetime.now(UTC).replace(tzinfo=None) + timedelta(days=1)
        await identity.store_refresh_token(
            user_id=user, token_hash="a" * 64, family_id="test-family", expires_at=expires
        )
        assert (await identity.lock_refresh_token("a" * 64))["revoked_at"] is None
        assert await identity.revoke_token_family("test-family") == 1
        assert (await identity.lock_refresh_token("a" * 64))["revoked_at"] is not None
        log = await audit.append_log(
            actor_id=user,
            action="course.publish",
            resource="course",
            resource_id=str(course),
            trace_id="sql-test",
            details={"title": "SQL thuần 🎓"},
        )
        await audit.append_security_event(
            actor_id=user, event_type=SecurityEventType.LOGIN_SUCCEEDED, trace_id="sql-test"
        )
        stored = await connection.scalar(
            text("SELECT details FROM audit_logs WHERE id = :id"), {"id": log}
        )
        assert json.loads(stored)["title"] == "SQL thuần 🎓"
        assert await courses.soft_delete(course)
        assert await courses.get(course) is None
        assert await content.get_lesson(lesson) is None
        assert await content.list_resources(lesson) == []
        assert await identity.soft_delete_user(user)
        assert await identity.get_user(user) is None
        assert await identity.get_credentials(email) is None
        assert await roles.get_role_codes(user) == []

    with pytest.raises(RuntimeError, match="abort use case"):
        async with engine.begin() as connection:
            await IdentityRepository(connection).create_user(
                email="rollback@example.com", username="rollback", hashed_password="test-hash"
            )
            await AuditRepository(connection).append_log(
                actor_id=None, action="test", resource="users", trace_id="rollback-test"
            )
            raise RuntimeError("abort use case")
    async with engine.connect() as connection:
        assert await IdentityRepository(connection).get_credentials("rollback@example.com") is None
        assert (
            await connection.scalar(
                text("SELECT COUNT(*) FROM audit_logs WHERE trace_id = :trace_id"),
                {"trace_id": "rollback-test"},
            )
            == 0
        )
