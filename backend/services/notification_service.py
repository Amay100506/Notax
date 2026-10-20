"""
Notification Service for NotifyIQ.
Core orchestration service managing the complete notification lifecycle:
- Ingestion, AI pipeline execution, and persistence
- Batch processing with exclusion handling
- Smart Inbox filtering and querying
- Attention summary aggregation (deadlines, high-priority, open actions, low confidence)
- Package exclusion management
- Quiet hours scheduling and deferred status tracking
- Data retention cleanup and per-app analytics
"""

import json
from datetime import datetime, timezone
from typing import Any, Optional, Union
from zoneinfo import ZoneInfo
from pydantic import BaseModel, Field

from backend.ai.deadline_extractor import parse_reference_time
from backend.ai.pipeline import AIPipeline
from backend.database.repository import Repository
from backend.utils.configuration import settings
from backend.utils.logging_config import logger


class InboxFilters(BaseModel):
    """Filter criteria for the Smart Inbox."""
    category: Optional[str] = None
    priority_level: Optional[str] = None
    package_name: Optional[str] = None
    search: Optional[str] = None
    action_detected: Optional[bool] = None
    deadline_detected: Optional[bool] = None
    is_duplicate: Optional[bool] = None
    needs_review: Optional[bool] = None
    is_unread: Optional[bool] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    limit: int = Field(default=50, ge=1, le=1000)
    offset: int = Field(default=0, ge=0)

    model_config = {"extra": "ignore"}


class InboxResult(BaseModel):
    """Result of a Smart Inbox query."""
    items: list[dict[str, Any]] = Field(default_factory=list)
    total_count: int = 0
    limit: int = 50
    offset: int = 0

    model_config = {"extra": "ignore"}


class AttentionSummary(BaseModel):
    """Aggregated attention summary for items requiring user focus."""
    overdue_deadlines: list[dict[str, Any]] = Field(default_factory=list)
    unread_high_priority: list[dict[str, Any]] = Field(default_factory=list)
    open_action_items: list[dict[str, Any]] = Field(default_factory=list)
    needs_review_items: list[dict[str, Any]] = Field(default_factory=list)
    overdue_count: int = 0
    unread_high_priority_count: int = 0
    open_action_count: int = 0
    needs_review_count: int = 0
    total_attention_count: int = 0

    @property
    def open_actions_count(self) -> int:
        """Alias for open_action_count."""
        return self.open_action_count

    @property
    def total_attention_needed(self) -> int:
        """Alias for total_attention_count."""
        return self.total_attention_count

    model_config = {"extra": "ignore"}


class BatchResult(BaseModel):
    """Summary of batch notification processing."""
    total: int = 0
    processed_count: int = 0
    failed_count: int = 0
    excluded_count: int = 0
    deferred_count: int = 0
    results: list[dict[str, Any]] = Field(default_factory=list)
    errors: list[dict[str, Any]] = Field(default_factory=list)

    @property
    def items(self) -> list[dict[str, Any]]:
        """Alias for processed results."""
        return self.results

    model_config = {"extra": "ignore"}


class NotificationService:
    """
    Central orchestration service for NotifyIQ.
    Coordinates between the AI pipeline, data repository, and application settings.
    """

    def __init__(
        self,
        repository: Optional[Repository] = None,
        pipeline: Optional[AIPipeline] = None,
    ):
        self.repository = repository or Repository()
        self.pipeline = pipeline or AIPipeline(repository=self.repository)

    # ----------------------------------------------------------------------
    # 1. Notification Ingestion & Lifecycle
    # ----------------------------------------------------------------------

    def process_and_persist(
        self,
        event: dict[str, Any],
        user_app_importance: Optional[dict[str, float]] = None,
        reference_time: Optional[Union[datetime, str]] = None,
        check_exclusion: bool = False,
    ) -> dict[str, Any]:
        """
        Process a notification through the AI pipeline and persist it.
        Wraps pipeline.process_notification with persist=True.

        If check_exclusion is True and the package is excluded, processing is skipped.
        If quiet hours are active, the notification is still captured and persisted,
        but marked as deferred.
        """
        package_name = event.get("package_name") or "unknown.package"
        if check_exclusion and self.is_package_excluded(package_name):
            logger.info("Package %s is in exclusion list; skipping processing", package_name)
            return {
                "id": "",
                "event_id": event.get("event_id", ""),
                "package_name": package_name,
                "status": "excluded",
                "is_excluded": True,
            }

        ref_dt: Optional[datetime] = None
        if isinstance(reference_time, datetime):
            ref_dt = reference_time
        elif isinstance(reference_time, str):
            ref_dt = parse_reference_time(reference_time)
        elif event.get("posted_at") or event.get("received_at"):
            ref_dt = parse_reference_time(event.get("posted_at") or event.get("received_at"))

        quiet = self.is_quiet_hours(check_time=ref_dt)

        if quiet:
            # Process without immediate persistence to annotate deferred reason
            processed = self.pipeline.process_notification(
                event,
                user_app_importance=user_app_importance,
                reference_time=ref_dt,
                persist=False,
            )
            deferred_reason = "Deferred: Received during quiet hours"
            reasons = list(processed.get("priority_reasons", []))
            if deferred_reason not in reasons:
                reasons.append(deferred_reason)
            processed["priority_reasons"] = reasons

            persisted = self.repository.create_notification(processed)
            persisted["is_deferred"] = True
            logger.info(
                "Processed & persisted deferred event %s (quiet hours active)",
                event.get("event_id"),
            )
            return persisted
        else:
            persisted = self.pipeline.process_notification(
                event,
                user_app_importance=user_app_importance,
                reference_time=ref_dt,
                persist=True,
            )
            persisted["is_deferred"] = False
            return persisted

    def batch_process(self, events: list[dict[str, Any]]) -> BatchResult:
        """
        Process multiple notification events, returning a structured summary.
        Excludes packages in the exclusion list and tracks deferred notifications.
        """
        result = BatchResult(total=len(events))

        for event in events:
            pkg = event.get("package_name") or ""
            if self.is_package_excluded(pkg):
                result.excluded_count += 1
                continue

            try:
                persisted = self.process_and_persist(event)
                result.processed_count += 1
                if persisted.get("is_deferred") or any(
                    "deferred" in str(r).lower()
                    for r in persisted.get("priority_reasons", [])
                ):
                    result.deferred_count += 1
                result.results.append(persisted)
            except Exception as exc:
                logger.error(
                    "Error processing event %s in batch: %s",
                    event.get("event_id", "unknown"),
                    exc,
                    exc_info=True,
                )
                result.failed_count += 1
                result.errors.append({
                    "event_id": event.get("event_id", "unknown"),
                    "error": str(exc),
                })

        return result

    def mark_read(self, notification_id: str) -> bool:
        """
        Mark notification as read.
        Returns True if updated successfully, False otherwise.
        """
        return self.repository.mark_notification_read(notification_id, is_read=True)

    def mark_unread(self, notification_id: str) -> bool:
        """
        Mark notification as unread.
        Returns True if updated successfully, False otherwise.
        """
        return self.repository.mark_notification_read(notification_id, is_read=False)

    # ----------------------------------------------------------------------
    # 2. Smart Inbox & Querying
    # ----------------------------------------------------------------------

    def get_smart_inbox(
        self,
        filters: Optional[Union[InboxFilters, dict[str, Any]]] = None,
        **kwargs: Any,
    ) -> InboxResult:
        """
        Smart inbox query with multi-criteria filtering, ranking, and pagination.
        Accepts InboxFilters instance, dictionary, or keyword arguments.
        """
        if filters is None:
            filters_obj = InboxFilters(**kwargs)
        elif isinstance(filters, dict):
            merged = {**filters, **kwargs}
            filters_obj = InboxFilters(**merged)
        elif isinstance(filters, InboxFilters):
            if kwargs:
                data = filters.model_dump()
                data.update(kwargs)
                filters_obj = InboxFilters(**data)
            else:
                filters_obj = filters
        else:
            raise TypeError(f"Invalid filters type: {type(filters)}")

        items, total_count = self.repository.list_notifications(
            limit=filters_obj.limit,
            offset=filters_obj.offset,
            category=filters_obj.category,
            priority_level=filters_obj.priority_level,
            package_name=filters_obj.package_name,
            action_detected=filters_obj.action_detected,
            deadline_detected=filters_obj.deadline_detected,
            is_duplicate=filters_obj.is_duplicate,
            search=filters_obj.search,
            start_date=filters_obj.start_date,
            end_date=filters_obj.end_date,
            is_unread=filters_obj.is_unread,
            needs_review=filters_obj.needs_review,
            confidence_threshold=settings.confidence_threshold,
        )

        for item in items:
            item["is_deferred"] = any(
                "deferred" in str(r).lower()
                for r in item.get("priority_reasons", [])
            )

        return InboxResult(
            items=items,
            total_count=total_count,
            limit=filters_obj.limit,
            offset=filters_obj.offset,
        )

    def get_attention_summary(
        self, reference_time: Optional[Union[datetime, str]] = None
    ) -> AttentionSummary:
        """
        Returns items needing immediate user attention:
        - Overdue deadlines
        - Unread high-priority notifications
        - Open action items
        - Low-confidence items needing review
        """
        if isinstance(reference_time, datetime):
            now_iso = reference_time.isoformat()
        elif isinstance(reference_time, str):
            now_iso = reference_time
        else:
            now_iso = datetime.now(timezone.utc).isoformat()

        overdue_deadlines = self.repository.get_overdue_deadlines(
            reference_time_iso=now_iso
        )
        unread_high = self.repository.get_unread_high_priority()
        open_actions = self.repository.list_actions(status="open")
        needs_review = self.repository.get_low_confidence_notifications(
            threshold=settings.confidence_threshold
        )

        return AttentionSummary(
            overdue_deadlines=overdue_deadlines,
            unread_high_priority=unread_high,
            open_action_items=open_actions,
            needs_review_items=needs_review,
            overdue_count=len(overdue_deadlines),
            unread_high_priority_count=len(unread_high),
            open_action_count=len(open_actions),
            needs_review_count=len(needs_review),
            total_attention_count=(
                len(overdue_deadlines)
                + len(unread_high)
                + len(open_actions)
                + len(needs_review)
            ),
        )

    # ----------------------------------------------------------------------
    # 3. Package Exclusions Management
    # ----------------------------------------------------------------------

    def manage_package_exclusions(self, excluded_packages: list[str]) -> list[str]:
        """
        Save app exclusion list via settings table.
        Normalizes package names, removes duplicates, and persists to DB.
        """
        cleaned = sorted(
            list(
                set(
                    pkg.strip()
                    for pkg in excluded_packages
                    if isinstance(pkg, str) and pkg.strip()
                )
            )
        )
        self.repository.set_setting("excluded_packages", json.dumps(cleaned))
        logger.info("Updated package exclusions list (%d packages)", len(cleaned))
        return cleaned

    def get_excluded_packages(self) -> list[str]:
        """Retrieve current exclusion list from settings table."""
        val = self.repository.get_setting("excluded_packages", "[]")
        try:
            parsed = json.loads(val or "[]")
            if isinstance(parsed, list):
                return [str(p) for p in parsed]
            return []
        except Exception:
            return []

    def is_package_excluded(self, package_name: str) -> bool:
        """Check if a package is currently excluded."""
        if not package_name:
            return False
        excluded_set = set(self.get_excluded_packages())
        return package_name.strip() in excluded_set

    # ----------------------------------------------------------------------
    # 4. Quiet Hours Configuration
    # ----------------------------------------------------------------------

    def set_quiet_hours(self, start_hour: int, end_hour: int) -> None:
        """
        Configure quiet hours (24-hour integers from 0 to 23).
        During quiet hours, notifications are still captured and persisted,
        but marked as deferred.
        """
        if not (0 <= start_hour <= 23 and 0 <= end_hour <= 23):
            raise ValueError(
                f"Quiet hours start_hour and end_hour must be between 0 and 23. Got start={start_hour}, end={end_hour}"
            )
        self.repository.set_setting("quiet_hours_start", str(start_hour))
        self.repository.set_setting("quiet_hours_end", str(end_hour))
        self.repository.set_setting("quiet_hours_enabled", "true")
        logger.info("Quiet hours configured: %02d:00 to %02d:00", start_hour, end_hour)

    def disable_quiet_hours(self) -> None:
        """Disables quiet hours."""
        self.repository.set_setting("quiet_hours_enabled", "false")
        logger.info("Quiet hours disabled")

    def get_quiet_hours(self) -> Optional[tuple[int, int]]:
        """
        Returns (start_hour, end_hour) if quiet hours are enabled, else None.
        """
        enabled = self.repository.get_setting("quiet_hours_enabled", "false")
        if enabled.lower() not in ("true", "1", "yes"):
            return None
        start = self.repository.get_setting("quiet_hours_start")
        end = self.repository.get_setting("quiet_hours_end")
        if start is None or end is None:
            return None
        try:
            return int(start), int(end)
        except ValueError:
            return None

    def is_quiet_hours(
        self, check_time: Optional[Union[datetime, str]] = None
    ) -> bool:
        """
        Check if the current time (or specified check_time) falls within quiet hours.
        Calculated using settings.timezone.
        """
        hours = self.get_quiet_hours()
        if hours is None:
            return False

        start_hour, end_hour = hours
        if start_hour == end_hour:
            return False

        if isinstance(check_time, str):
            dt = parse_reference_time(check_time)
        elif isinstance(check_time, datetime):
            dt = check_time
        else:
            try:
                tz = ZoneInfo(settings.timezone)
            except Exception:
                tz = timezone.utc
            dt = datetime.now(tz)

        current_hour = dt.hour
        if start_hour < end_hour:
            return start_hour <= current_hour < end_hour
        else:
            # Overnight span (e.g., 22:00 to 07:00)
            return current_hour >= start_hour or current_hour < end_hour

    # ----------------------------------------------------------------------
    # 5. Retention Cleanup & Analytics
    # ----------------------------------------------------------------------

    def cleanup_expired_retention(self) -> int:
        """
        Run retention cleanup, removing notifications past their retention date.
        Returns the number of deleted records.
        """
        deleted_count = self.repository.cleanup_expired_retention()
        logger.info("Expired retention cleanup: deleted %d records", deleted_count)
        return deleted_count

    def get_notification_stats_by_app(self) -> list[dict[str, Any]]:
        """
        Retrieve comprehensive per-app notification statistics:
        volume, priorities, actions, deadlines, unread counts, and latest activity.
        """
        return self.repository.get_notification_stats_by_app()
