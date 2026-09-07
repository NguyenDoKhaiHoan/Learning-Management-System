from enum import StrEnum


class LessonType(StrEnum):
    VIDEO = "VIDEO"
    ARTICLE = "ARTICLE"
    DOCUMENT = "DOCUMENT"
    LIVE = "LIVE"


class ResourceType(StrEnum):
    FILE = "FILE"
    LINK = "LINK"
