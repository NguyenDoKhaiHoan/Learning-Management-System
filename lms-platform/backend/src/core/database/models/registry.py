"""Import every persistence model before exposing metadata to Alembic."""

from src.core.database.models.base import Base
from src.modules.audit_security.infrastructure.models import AuditLog, SecurityEvent
from src.modules.course.infrastructure.models import Course
from src.modules.enrollment.infrastructure.models import CourseStaff, Enrollment
from src.modules.identity_access.infrastructure.models import RefreshToken, User
from src.modules.learning_content.infrastructure.models import CourseModule, Lesson, LessonResource
from src.modules.user_role.infrastructure.models import Permission, Role, RolePermission, UserRole

__all__ = [
    "Base",
    "AuditLog",
    "SecurityEvent",
    "Course",
    "CourseStaff",
    "Enrollment",
    "RefreshToken",
    "User",
    "CourseModule",
    "Lesson",
    "LessonResource",
    "Permission",
    "Role",
    "RolePermission",
    "UserRole",
]
