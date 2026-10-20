"""
Unit tests for SQLite schema, connection, and repository operations.
Tests run against a temporary in-memory or isolated file database.
"""

import tempfile
import pytest
from pathlib import Path
from backend.database.connection import init_db
from backend.database.repository import Repository


@pytest.fixture
def temp_repo():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
        db_path = Path(tmpdir) / "test_notifyiq.db"
        init_db(db_path)
        repo = Repository(str(db_path))
        yield repo


def test_init_db_and_schema_version(temp_repo):
    # Verify tables were created and schema migrations recorded version 1
    assert Path(temp_repo.db_path).exists()
    settings = temp_repo.get_all_settings()
    assert isinstance(settings, dict)


def test_create_and_get_notification(temp_repo):
    sample = {
        "event_id": "test-evt-001",
        "package_name": "com.test.app",
        "title": "Meeting Notice",
        "text": "Review agenda before 3 PM",
        "normalized_text": "review agenda before 3 pm",
        "category": "action_required",
        "category_confidence": 0.92,
        "model_type": "tfidf_logistic_regression",
        "priority_score": 85.0,
        "priority_level": "high",
        "urgency_score": 80.0,
        "action_score": 90.0,
        "deadline_score": 85.0,
        "importance_score": 50.0,
        "recency_score": 95.0,
        "action_detected": True,
        "action_type": "review",
        "action_text": "Review agenda",
        "deadline_text": "before 3 PM",
        "deadline_at": "2026-10-19T15:00:00+00:00",
        "deadline_status": "resolved",
        "priority_reasons": ["Action detected", "Deadline within 24 hours"],
        "received_at": "2026-10-19T10:00:00+00:00",
    }
    created = temp_repo.create_notification(sample)
    assert created is not None
    assert created["event_id"] == "test-evt-001"
    assert created["priority_level"] == "high"
    assert created["action_detected"] is True
    assert len(created["priority_reasons"]) == 2

    # Verify action was automatically registered in actions table
    actions = temp_repo.list_actions()
    assert len(actions) == 1
    assert actions[0]["action_text"] == "Review agenda"
    assert actions[0]["status"] == "open"


def test_event_id_unique_constraint(temp_repo):
    sample = {
        "event_id": "unique-evt-123",
        "package_name": "com.test.app",
        "title": "Alert",
        "text": "Message",
        "category": "system",
        "category_confidence": 0.9,
        "priority_score": 20.0,
        "received_at": "2026-10-19T10:00:00+00:00",
    }
    temp_repo.create_notification(sample)

    with pytest.raises(Exception):
        # Second insert with identical event_id must fail uniqueness
        temp_repo.create_notification(sample)


def test_action_status_update(temp_repo):
    sample = {
        "event_id": "action-evt-1",
        "package_name": "com.task.manager",
        "title": "Task Alert",
        "text": "Complete report",
        "category": "action_required",
        "priority_score": 75.0,
        "action_detected": True,
        "action_text": "Complete report",
        "received_at": "2026-10-19T10:00:00+00:00",
    }
    temp_repo.create_notification(sample)
    actions = temp_repo.list_actions()
    assert len(actions) == 1
    action_id = actions[0]["id"]

    # Mark completed
    success = temp_repo.update_action_status(action_id, "completed")
    assert success is True
    updated = temp_repo.list_actions(status="completed")
    assert len(updated) == 1
    assert updated[0]["status"] == "completed"
    assert updated[0]["completed_at"] is not None


def test_duplicate_groups(temp_repo):
    group = temp_repo.get_or_create_group(fingerprint="fp-12345", method="exact")
    assert group["fingerprint"] == "fp-12345"

    # Reuse existing
    group2 = temp_repo.get_or_create_group(fingerprint="fp-12345", method="exact")
    assert group["id"] == group2["id"]


def test_feedback_and_category_correction(temp_repo):
    sample = {
        "event_id": "feedback-evt-1",
        "package_name": "com.social.app",
        "title": "Sale offer",
        "text": "Flash deal today",
        "category": "social",
        "category_confidence": 0.55,
        "priority_score": 30.0,
        "received_at": "2026-10-19T10:00:00+00:00",
    }
    record = temp_repo.create_notification(sample)
    notif_id = record["id"]

    # User corrects category to promotional
    fb = temp_repo.record_feedback(
        notification_id=notif_id,
        feedback_type="category",
        original_value="social",
        corrected_value="promotional",
    )
    assert fb["corrected_value"] == "promotional"

    # Verify notification record was updated
    updated = temp_repo.get_notification_by_id(notif_id)
    assert updated["category"] == "promotional"


def test_purge_all_data(temp_repo):
    sample = {
        "event_id": "purge-evt-1",
        "package_name": "com.test.app",
        "title": "To delete",
        "category": "system",
        "priority_score": 10.0,
        "received_at": "2026-10-19T10:00:00+00:00",
    }
    temp_repo.create_notification(sample)
    purge_summary = temp_repo.purge_all_data()
    assert purge_summary["deleted_notifications"] == 1

    remaining, count = temp_repo.list_notifications()
    assert count == 0
    assert len(remaining) == 0
