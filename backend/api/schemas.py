"""
Pydantic API request and response schemas for NotifyIQ.
"""

from typing import Any, Optional
from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str = "healthy"
    model_loaded: bool
    model_type: str
    db_initialized: bool
    version: str = "1.0.0"


class NotificationImportItem(BaseModel):
    schema_version: int = Field(default=1, ge=1)
    event_id: str = Field(min_length=1, max_length=128)
    package_name: str = Field(min_length=1, max_length=256)
    title: Optional[str] = Field(default="", max_length=512)
    text: Optional[str] = Field(default="", max_length=4096)
    posted_at: str
    event_type: str = Field(default="posted")

    model_config = {"extra": "ignore"}


class NotificationImportBatch(BaseModel):
    notifications: list[NotificationImportItem]


class ProcessNotificationRequest(BaseModel):
    notification: NotificationImportItem
    persist: bool = True


class NotificationResponse(BaseModel):
    id: str
    event_id: str
    package_name: str
    title: Optional[str] = None
    text: Optional[str] = None
    category: str
    category_confidence: float
    model_type: str
    priority_score: float
    priority_level: str
    urgency_score: float
    action_score: float
    deadline_score: float
    importance_score: float
    recency_score: float
    action_detected: bool
    action_type: Optional[str] = None
    action_text: Optional[str] = None
    deadline_text: Optional[str] = None
    deadline_at: Optional[str] = None
    deadline_status: str
    priority_reasons: list[str]
    duplicate_group_id: Optional[str] = None
    is_duplicate: bool
    received_at: str
    processed_at: str
    is_read: bool = False


class NotificationListResponse(BaseModel):
    items: list[NotificationResponse]
    total_count: int
    limit: int
    offset: int


class ActionItemResponse(BaseModel):
    id: str
    notification_id: str
    notification_title: Optional[str] = None
    package_name: Optional[str] = None
    action_type: str
    action_text: str
    deadline_at: Optional[str] = None
    status: str
    priority_score: Optional[float] = None
    priority_level: Optional[str] = None
    created_at: str
    completed_at: Optional[str] = None


class ActionStatusUpdate(BaseModel):
    status: str = Field(pattern="^(open|completed|dismissed)$")


class FeedbackRequest(BaseModel):
    notification_id: str
    feedback_type: str = Field(pattern="^(category|priority_level|action|deadline)$")
    original_value: str
    corrected_value: str


class FeedbackResponse(BaseModel):
    id: str
    notification_id: str
    feedback_type: str
    original_value: str
    corrected_value: str
    created_at: str


class SettingsUpdate(BaseModel):
    settings: dict[str, str]


class PurgeResponse(BaseModel):
    status: str = "purged"
    deleted_notifications: int
    deleted_actions: int
    deleted_feedback: int
    deleted_groups: int
