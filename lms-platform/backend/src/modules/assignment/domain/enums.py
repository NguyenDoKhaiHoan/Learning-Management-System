from enum import StrEnum


class AssignmentStatus(StrEnum):
    DRAFT = "DRAFT"
    PUBLISHED = "PUBLISHED"
    CLOSED = "CLOSED"
    ARCHIVED = "ARCHIVED"


class SubmissionStatus(StrEnum):
    SUBMITTED = "SUBMITTED"
    LATE = "LATE"
