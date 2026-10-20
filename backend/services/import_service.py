"""
JSON Import and Export Service for NotifyIQ.
Validates incoming Android notification events, handles duplicates,
generates import reports, and exports stored notifications safely.
"""

import csv
import io
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Optional
from pydantic import BaseModel, Field, ValidationError
from backend.database.repository import Repository
from backend.utils.logging_config import logger


class AndroidNotificationEvent(BaseModel):
    """Schema validation for an incoming notification event from Android."""
    schema_version: int = Field(default=1, ge=1)
    event_id: str = Field(min_length=1, max_length=128)
    package_name: str = Field(min_length=1, max_length=256)
    title: Optional[str] = Field(default="", max_length=512)
    text: Optional[str] = Field(default="", max_length=4096)
    posted_at: str
    event_type: str = Field(default="posted")

    model_config = {"extra": "ignore"}


class ImportReport(BaseModel):
    """Report generated after importing a batch of notification events."""
    total_records: int = 0
    accepted_count: int = 0
    rejected_count: int = 0
    already_processed_count: int = 0
    accepted_records: list[dict[str, Any]] = []
    rejected_records: list[dict[str, Any]] = []
    warnings: list[str] = []


class ImportService:
    def __init__(self, repository: Optional[Repository] = None):
        self.repository = repository or Repository()

    def validate_and_filter_events(
        self, raw_input: str | list[dict[str, Any]] | dict[str, Any]
    ) -> ImportReport:
        """
        Parses raw JSON string, list of dicts, or single dict.
        Validates against AndroidNotificationEvent.
        Checks for already existing event IDs in the repository.
        Returns structured ImportReport.
        """
        report = ImportReport()

        # Step 1: Parse input to list of items
        items: list[Any] = []
        if isinstance(raw_input, str):
            try:
                parsed = json.loads(raw_input)
                items = parsed if isinstance(parsed, list) else [parsed]
            except Exception as e:
                report.warnings.append(f"JSON parsing error: {str(e)}")
                return report
        elif isinstance(raw_input, list):
            items = raw_input
        elif isinstance(raw_input, dict):
            items = [raw_input]
        else:
            report.warnings.append(f"Unsupported input type: {type(raw_input)}")
            return report

        report.total_records = len(items)

        # Step 2: Validate each item
        for item in items:
            if not isinstance(item, dict):
                report.rejected_count += 1
                report.rejected_records.append({
                    "record": str(item)[:100],
                    "reason": "Record is not a valid JSON object"
                })
                continue

            try:
                validated = AndroidNotificationEvent(**item)
            except ValidationError as ve:
                report.rejected_count += 1
                report.rejected_records.append({
                    "event_id": item.get("event_id", "unknown"),
                    "reason": f"Validation failed: {ve.errors()[0]['msg']}"
                })
                continue

            # Validate ISO timestamp
            try:
                # Replace 'Z' with '+00:00' for broad python fromisoformat compatibility
                ts_str = validated.posted_at.replace("Z", "+00:00")
                datetime.fromisoformat(ts_str)
            except Exception:
                report.rejected_count += 1
                report.rejected_records.append({
                    "event_id": validated.event_id,
                    "reason": f"Invalid ISO 8601 timestamp: {validated.posted_at}"
                })
                continue

            # Check if event was already recorded in database
            existing = self.repository.get_notification_by_event_id(validated.event_id)
            if existing:
                report.already_processed_count += 1
                continue

            report.accepted_count += 1
            report.accepted_records.append(validated.model_dump())

        logger.info(
            "Import batch evaluated: total=%d, accepted=%d, rejected=%d, existing=%d",
            report.total_records,
            report.accepted_count,
            report.rejected_count,
            report.already_processed_count,
        )
        return report

    def import_file(self, file_path: Path | str) -> ImportReport:
        """Reads a JSON file from disk and runs import validation."""
        path = Path(file_path)
        if not path.exists():
            report = ImportReport()
            report.warnings.append(f"File not found: {file_path}")
            return report

        with open(path, "r", encoding="utf-8") as f:
            content = f.read()

        return self.validate_and_filter_events(content)

    def export_notifications_json(self, limit: int = 1000) -> str:
        """Exports processed notifications to JSON format."""
        records, _ = self.repository.list_notifications(limit=limit)
        return json.dumps(records, indent=2, default=str)

    def export_notifications_csv(self, limit: int = 1000) -> str:
        """Exports processed notifications to CSV format."""
        records, _ = self.repository.list_notifications(limit=limit)
        if not records:
            return ""

        output = io.StringIO()
        fieldnames = [
            "id",
            "event_id",
            "package_name",
            "title",
            "category",
            "category_confidence",
            "priority_score",
            "priority_level",
            "action_detected",
            "action_type",
            "deadline_text",
            "deadline_status",
            "is_duplicate",
            "received_at",
            "processed_at",
        ]
        writer = csv.DictWriter(output, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for r in records:
            writer.writerow(r)
        return output.getvalue()
