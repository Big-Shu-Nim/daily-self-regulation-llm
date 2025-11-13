"""Domain layer exports."""

from .cleaned_documents import (
    CleanedCalendarDocument,
    CleanedDocument,
    CleanedNaverDocument,
    CleanedNotionDocument,
)
from .documents import (
    CalendarDocument,
    NaverPostDocument,
    NotionPageDocument,
    UserDocument,
)
from .embedded_documents import (
    EmbeddedCalendarDocument,
    EmbeddedDocument,
    EmbeddedNaverDocument,
    EmbeddedNotionDocument,
)
from .feedback_documents import (
    DailyFeedbackDocument,
    FeedbackDocument,
    MonthlyFeedbackDocument,
    PublicDailyFeedbackDocument,
    WeeklyFeedbackDocument,
)
from .types import DataCategory

__all__ = [
    # Base
    "DataCategory",
    # User
    "UserDocument",
    # Raw documents
    "CalendarDocument",
    "NotionPageDocument",
    "NaverPostDocument",
    # Cleaned documents
    "CleanedDocument",
    "CleanedCalendarDocument",
    "CleanedNotionDocument",
    "CleanedNaverDocument",
    # Embedded documents
    "EmbeddedDocument",
    "EmbeddedCalendarDocument",
    "EmbeddedNotionDocument",
    "EmbeddedNaverDocument",
    # Feedback documents
    "FeedbackDocument",
    "DailyFeedbackDocument",
    "WeeklyFeedbackDocument",
    "MonthlyFeedbackDocument",
    "PublicDailyFeedbackDocument",
]
