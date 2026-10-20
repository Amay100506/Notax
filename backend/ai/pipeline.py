"""
End-to-End AI Processing Pipeline for NotifyIQ.
Orchestrates:
1. Text Preprocessing & Redaction
2. Category Classification (ML with rule fallback)
3. Action Extraction
4. Deadline Extraction & Timezone Resolution
5. Priority Scoring & Explainability
6. Duplicate Detection (Exact & Near)
"""

import uuid
from datetime import datetime, timezone
from typing import Any, Optional
from pydantic import BaseModel
from backend.ai.action_extractor import extract_action
from backend.ai.classifier import CategoryClassifier
from backend.ai.deadline_extractor import extract_deadline
from backend.ai.duplicate_detector import DuplicateDetector
from backend.ai.preprocess import preprocess_text
from backend.ai.priority_engine import score_priority
from backend.database.repository import Repository
from backend.utils.configuration import settings
from backend.utils.logging_config import logger


class ProcessedNotification(BaseModel):
    id: str
    event_id: str
    package_name: str
    title: str
    text: str
    normalized_text: str
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
    retention_expires_at: Optional[str] = None
    is_read: bool = False


class AIPipeline:
    def __init__(
        self,
        classifier: Optional[CategoryClassifier] = None,
        duplicate_detector: Optional[DuplicateDetector] = None,
        repository: Optional[Repository] = None,
    ):
        self.repository = repository or Repository()
        self.classifier = classifier or CategoryClassifier()
        self.duplicate_detector = duplicate_detector or DuplicateDetector(self.repository)

    def process_notification(
        self,
        event: dict[str, Any],
        user_app_importance: Optional[dict[str, float]] = None,
        reference_time: Optional[datetime] = None,
        persist: bool = False,
    ) -> dict[str, Any]:
        """
        Processes a raw/validated notification event through all pipeline stages.
        If persist=True, automatically saves to SQLite via Repository.
        """
        event_id = event.get("event_id") or str(uuid.uuid4())
        package_name = event.get("package_name") or "unknown.package"
        raw_title = event.get("title") or ""
        raw_text = event.get("text") or ""
        received_at = event.get("posted_at") or event.get("received_at") or datetime.now(timezone.utc).isoformat()
        
        # 1. Text Preprocessing & Privacy Redaction
        title_prep = preprocess_text(raw_title, apply_redaction=settings.redaction_enabled)
        text_prep = preprocess_text(raw_text, apply_redaction=settings.redaction_enabled)

        # 2. Category Classification
        clf_result = self.classifier.predict(
            text=text_prep.normalized_text,
            title=title_prep.normalized_text,
            package_name=package_name,
        )

        # 3. Action Extraction
        action_result = extract_action(
            text=text_prep.redacted_text,
            title=title_prep.redacted_text,
        )

        # 4. Deadline Extraction
        deadline_result = extract_deadline(
            text=text_prep.redacted_text,
            title=title_prep.redacted_text,
            reference_time_str=received_at,
        )

        # 5. Duplicate Detection
        dup_result = self.duplicate_detector.check_duplicate(
            package_name=package_name,
            title=title_prep.normalized_text,
            text=text_prep.normalized_text,
        )

        # 6. Priority Scoring & Explainability
        priority_result = score_priority(
            category=clf_result.category,
            text=text_prep.normalized_text,
            package_name=package_name,
            received_at_iso=received_at,
            action_detected=action_result.action_detected,
            action_certainty=action_result.action_certainty,
            deadline_detected=deadline_result.deadline_detected,
            time_remaining_seconds=deadline_result.time_remaining_seconds,
            is_overdue=deadline_result.is_overdue,
            user_app_importance=user_app_importance,
            reference_time=reference_time,
        )

        # Build output structure
        record_id = str(uuid.uuid4())
        processed_at = datetime.now(timezone.utc).isoformat()
        
        output = {
            "id": record_id,
            "event_id": event_id,
            "package_name": package_name,
            "title": title_prep.redacted_text,
            "text": text_prep.redacted_text,
            "normalized_text": f"{title_prep.normalized_text} {text_prep.normalized_text}".strip(),
            "category": clf_result.category,
            "category_confidence": clf_result.confidence,
            "model_type": clf_result.model_type,
            "priority_score": priority_result.priority_score,
            "priority_level": priority_result.priority_level,
            "urgency_score": priority_result.components.urgency_score,
            "action_score": priority_result.components.action_score,
            "deadline_score": priority_result.components.deadline_score,
            "importance_score": priority_result.components.importance_score,
            "recency_score": priority_result.components.recency_score,
            "action_detected": action_result.action_detected,
            "action_type": action_result.action_type,
            "action_text": action_result.action_text,
            "deadline_text": deadline_result.deadline_text,
            "deadline_at": deadline_result.deadline_at,
            "deadline_status": deadline_result.resolution_status,
            "priority_reasons": priority_result.priority_reasons,
            "duplicate_group_id": dup_result.duplicate_group_id,
            "is_duplicate": dup_result.is_duplicate,
            "received_at": received_at,
            "processed_at": processed_at,
            "retention_expires_at": None,
            "is_read": False,
        }

        # 7. Persistence (if requested)
        if persist:
            created = self.repository.create_notification(output)
            logger.info("Processed & persisted event %s (cat=%s, prio=%.1f)", event_id, output["category"], output["priority_score"])
            return created

        return output
