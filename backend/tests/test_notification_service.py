"""
Unit tests for NotificationService.
Tests cover:
- process_and_persist lifecycle
- batch_process with exclusions and failure handling
- mark_read and mark_unread
- get_smart_inbox with multi-criteria filters and pagination
- get_attention_summary (overdue, high priority, actions, low confidence review)
- manage_package_exclusions, get_excluded_packages, is_package_excluded
- cleanup_expired_retention
- set_quiet_hours, is_quiet_hours, deferred status marking
- get_notification_stats_by_app
"""

import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
import pytest

from backend.ai.pipeline import AIPipeline
from backend.database.connection import init_db
from backend.database.repository import Repository
from backend.services.notification_service import (
    AttentionSummary,
    BatchResult,
    InboxFilters,
    InboxResult,
    NotificationService,
)


@pytest.fixture
def service():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
        db_path = Path(tmpdir) / "test_service.db"
        init_db(db_path)
        repo = Repository(str(db_path))
        pipeline = AIPipeline(repository=repo)
        yield NotificationService(repository=repo, pipeline=pipeline)


def test_process_and_persist(service):
    event = {
        "event_id": "svc-001",
        "package_name": "com.slack",
        "title": "Action Required",
        "text": "Submit the quarterly financial review by tomorrow 5 PM.",
        "posted_at": "2026-10-19T10:00:00+05:30",
    }
    result = service.process_and_persist(event)

    assert result["event_id"] == "svc-001"
    assert result["category"] == "action_required"
    assert result["action_detected"] is True
    assert result["deadline_status"] == "resolved"
    assert result["is_deferred"] is False

    # Check persistence in DB
    persisted = service.repository.get_notification_by_event_id("svc-001")
    assert persisted is not None
    assert persisted["id"] == result["id"]
    assert persisted["is_read"] is False


def test_mark_read_and_unread(service):
    event = {
        "event_id": "svc-read-01",
        "package_name": "com.whatsapp",
        "title": "Family Chat",
        "text": "Dinner tonight at 8?",
        "posted_at": "2026-10-19T10:00:00+00:00",
    }
    created = service.process_and_persist(event)
    notif_id = created["id"]

    # Mark as read
    success = service.mark_read(notif_id)
    assert success is True

    record = service.repository.get_notification_by_id(notif_id)
    assert record["is_read"] is True

    # Mark as unread
    success = service.mark_unread(notif_id)
    assert success is True
    record = service.repository.get_notification_by_id(notif_id)
    assert record["is_read"] is False


def test_package_exclusions(service):
    # Initially no exclusions
    assert service.get_excluded_packages() == []
    assert service.is_package_excluded("com.facebook.orca") is False

    # Add exclusions
    updated = service.manage_package_exclusions(["com.facebook.orca", "com.instagram.android", " com.facebook.orca "])
    assert "com.facebook.orca" in updated
    assert "com.instagram.android" in updated
    assert len(updated) == 2

    assert service.is_package_excluded("com.facebook.orca") is True
    assert service.is_package_excluded("com.instagram.android") is True
    assert service.is_package_excluded("com.slack") is False


def test_batch_process_with_exclusions(service):
    service.manage_package_exclusions(["com.spam.promos"])

    events = [
        {
            "event_id": "batch-01",
            "package_name": "com.google.android.gm",
            "title": "Flight Confirmation",
            "text": "Your flight departs tomorrow at 10 AM.",
            "posted_at": "2026-10-19T10:00:00+00:00",
        },
        {
            "event_id": "batch-02",
            "package_name": "com.spam.promos",
            "title": "50% Off Sale",
            "text": "Big sale happening now!",
            "posted_at": "2026-10-19T10:00:00+00:00",
        },
        {
            "event_id": "batch-03",
            "package_name": "com.slack",
            "title": "Urgent Security Alert",
            "text": "Password change required immediately.",
            "posted_at": "2026-10-19T10:00:00+00:00",
        },
    ]

    res = service.batch_process(events)
    assert isinstance(res, BatchResult)
    assert res.total == 3
    assert res.processed_count == 2
    assert res.excluded_count == 1
    assert res.failed_count == 0
    assert len(res.results) == 2
    assert len(res.items) == 2


def test_quiet_hours_configuration_and_check(service):
    # Test setting valid quiet hours
    service.set_quiet_hours(22, 7)
    assert service.get_quiet_hours() == (22, 7)

    # 23:00 is during quiet hours (22:00 - 07:00)
    t_23 = datetime(2026, 10, 19, 23, 0, tzinfo=timezone.utc)
    assert service.is_quiet_hours(check_time=t_23) is True

    # 03:00 is during quiet hours
    t_03 = datetime(2026, 10, 20, 3, 0, tzinfo=timezone.utc)
    assert service.is_quiet_hours(check_time=t_03) is True

    # 12:00 is NOT during quiet hours
    t_12 = datetime(2026, 10, 20, 12, 0, tzinfo=timezone.utc)
    assert service.is_quiet_hours(check_time=t_12) is False

    # Test day quiet hours (13:00 to 15:00)
    service.set_quiet_hours(13, 15)
    t_14 = datetime(2026, 10, 20, 14, 0, tzinfo=timezone.utc)
    assert service.is_quiet_hours(check_time=t_14) is True
    assert service.is_quiet_hours(check_time=t_12) is False

    # Test invalid hours raise ValueError
    with pytest.raises(ValueError):
        service.set_quiet_hours(-1, 8)
    with pytest.raises(ValueError):
        service.set_quiet_hours(8, 25)

    # Test disable quiet hours
    service.disable_quiet_hours()
    assert service.is_quiet_hours(check_time=t_14) is False


def test_process_during_quiet_hours_deferred(service):
    # Set quiet hours to cover 10:00
    service.set_quiet_hours(9, 12)

    event = {
        "event_id": "quiet-01",
        "package_name": "com.slack",
        "title": "Update",
        "text": "Team sync at 11 AM",
        "posted_at": "2026-10-19T10:00:00+00:00",
    }
    ref_time = datetime(2026, 10, 19, 10, 30, tzinfo=timezone.utc)
    result = service.process_and_persist(event, reference_time=ref_time)

    assert result["is_deferred"] is True
    assert any("deferred" in r.lower() for r in result["priority_reasons"])

    # Persisted record should reflect the deferred reason
    persisted = service.repository.get_notification_by_event_id("quiet-01")
    assert any("deferred" in r.lower() for r in persisted["priority_reasons"])


def test_smart_inbox_filtering(service):
    # Ingest diverse notifications
    n1 = {
        "event_id": "inbox-01",
        "package_name": "com.whatsapp",
        "title": "Meeting notes",
        "text": "Please submit your budget request by Friday.",
        "posted_at": "2026-10-19T09:00:00+00:00",
    }
    n2 = {
        "event_id": "inbox-02",
        "package_name": "com.promo.deals",
        "title": "Huge Sale",
        "text": "Get 70% off selected items today!",
        "posted_at": "2026-10-19T10:00:00+00:00",
    }
    n3 = {
        "event_id": "inbox-03",
        "package_name": "com.bank.app",
        "title": "Security OTP",
        "text": "Your one time password is 948271. Do not share.",
        "posted_at": "2026-10-19T11:00:00+00:00",
    }

    r1 = service.process_and_persist(n1)
    service.process_and_persist(n2)
    service.process_and_persist(n3)

    # 1. Total inbox
    res = service.get_smart_inbox()
    assert isinstance(res, InboxResult)
    assert res.total_count == 3
    assert len(res.items) == 3

    # 2. Filter by search text
    res_search = service.get_smart_inbox(InboxFilters(search="OTP"))
    assert res_search.total_count == 1
    assert res_search.items[0]["package_name"] == "com.bank.app"

    # 3. Filter by package_name
    res_pkg = service.get_smart_inbox(InboxFilters(package_name="com.whatsapp"))
    assert res_pkg.total_count == 1
    assert res_pkg.items[0]["event_id"] == "inbox-01"

    # 4. Filter by action_detected
    res_act = service.get_smart_inbox(InboxFilters(action_detected=True))
    assert res_act.total_count >= 1
    assert any(item["event_id"] == "inbox-01" for item in res_act.items)

    # 5. Filter unread vs read
    service.mark_read(r1["id"])
    res_unread = service.get_smart_inbox(InboxFilters(is_unread=True))
    assert res_unread.total_count == 2
    assert not any(item["id"] == r1["id"] for item in res_unread.items)

    res_read = service.get_smart_inbox(InboxFilters(is_unread=False))
    assert res_read.total_count == 1
    assert res_read.items[0]["id"] == r1["id"]

    # 6. Pagination
    res_page = service.get_smart_inbox(InboxFilters(limit=1, offset=0))
    assert len(res_page.items) == 1
    assert res_page.total_count == 3


def test_attention_summary(service):
    # 1. Overdue deadline notification
    past_deadline = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()
    service.repository.create_notification({
        "event_id": "overdue-01",
        "package_name": "com.work.jira",
        "title": "Task Overdue",
        "text": "Submit review",
        "normalized_text": "submit review",
        "category": "action_required",
        "category_confidence": 0.95,
        "model_type": "test",
        "priority_score": 88.0,
        "priority_level": "high",
        "urgency_score": 90.0,
        "action_score": 90.0,
        "deadline_score": 90.0,
        "importance_score": 50.0,
        "recency_score": 80.0,
        "action_detected": True,
        "action_type": "review",
        "action_text": "Submit review",
        "deadline_text": "2 hours ago",
        "deadline_at": past_deadline,
        "deadline_status": "resolved",
        "priority_reasons": ["Urgent"],
        "received_at": past_deadline,
        "is_read": False,
    })

    # 2. Low confidence notification needing review (< 0.60)
    service.repository.create_notification({
        "event_id": "low-conf-01",
        "package_name": "com.unknown.app",
        "title": "Ambiguous message",
        "text": "Check this thing",
        "normalized_text": "check this thing",
        "category": "system",
        "category_confidence": 0.42,
        "model_type": "test",
        "priority_score": 30.0,
        "priority_level": "low",
        "urgency_score": 20.0,
        "action_score": 20.0,
        "deadline_score": 0.0,
        "importance_score": 20.0,
        "recency_score": 50.0,
        "received_at": datetime.now(timezone.utc).isoformat(),
        "is_read": False,
    })

    summary = service.get_attention_summary()
    assert isinstance(summary, AttentionSummary)
    assert summary.overdue_count >= 1
    assert len(summary.overdue_deadlines) >= 1
    assert summary.unread_high_priority_count >= 1
    assert summary.open_action_count >= 1
    assert summary.needs_review_count >= 1
    assert summary.total_attention_count >= 4
    assert summary.total_attention_needed == summary.total_attention_count
    assert summary.open_actions_count == summary.open_action_count


def test_cleanup_expired_retention(service):
    now = datetime.now(timezone.utc)
    past = (now - timedelta(days=1)).isoformat()
    future = (now + timedelta(days=30)).isoformat()

    # Expired notification
    service.repository.create_notification({
        "event_id": "expired-01",
        "package_name": "com.test",
        "category": "promotional",
        "category_confidence": 0.9,
        "model_type": "rule",
        "priority_score": 10.0,
        "priority_level": "low",
        "urgency_score": 10.0,
        "action_score": 0.0,
        "deadline_score": 0.0,
        "importance_score": 10.0,
        "recency_score": 10.0,
        "received_at": past,
        "retention_expires_at": past,
    })

    # Non-expired notification
    service.repository.create_notification({
        "event_id": "valid-01",
        "package_name": "com.test",
        "category": "promotional",
        "category_confidence": 0.9,
        "model_type": "rule",
        "priority_score": 10.0,
        "priority_level": "low",
        "urgency_score": 10.0,
        "action_score": 0.0,
        "deadline_score": 0.0,
        "importance_score": 10.0,
        "recency_score": 10.0,
        "received_at": past,
        "retention_expires_at": future,
    })

    deleted = service.cleanup_expired_retention()
    assert deleted == 1

    assert service.repository.get_notification_by_event_id("expired-01") is None
    assert service.repository.get_notification_by_event_id("valid-01") is not None


def test_notification_stats_by_app(service):
    events = [
        {
            "event_id": "stats-01",
            "package_name": "com.google.gmail",
            "title": "Meeting with Lead",
            "text": "Submit project proposal before tomorrow 4 PM.",
            "posted_at": "2026-10-19T10:00:00+00:00",
        },
        {
            "event_id": "stats-02",
            "package_name": "com.google.gmail",
            "title": "Newsletter",
            "text": "Weekly tech digest.",
            "posted_at": "2026-10-19T11:00:00+00:00",
        },
        {
            "event_id": "stats-03",
            "package_name": "com.slack",
            "title": "Deployment notice",
            "text": "Release 1.2 deployed to staging.",
            "posted_at": "2026-10-19T12:00:00+00:00",
        },
    ]

    service.batch_process(events)
    stats = service.get_notification_stats_by_app()

    assert len(stats) >= 2
    gmail_stat = next(s for s in stats if s["package_name"] == "com.google.gmail")
    assert gmail_stat["total_notifications"] == 2
    assert gmail_stat["action_count"] >= 1

    slack_stat = next(s for s in stats if s["package_name"] == "com.slack")
    assert slack_stat["total_notifications"] == 1
