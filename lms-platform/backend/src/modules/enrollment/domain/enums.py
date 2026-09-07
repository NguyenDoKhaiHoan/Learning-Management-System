from enum import StrEnum


class EnrollmentStatus(StrEnum):
    PENDING = "PENDING"
    ACTIVE = "ACTIVE"
    SUSPENDED = "SUSPENDED"
    COMPLETED = "COMPLETED"


class CourseStaffRole(StrEnum):
    INSTRUCTOR = "INSTRUCTOR"
    ASSISTANT = "ASSISTANT"
