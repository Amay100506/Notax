"""
Unit tests for NotifyIQ AI Daily Digest & Executive Briefing.
"""

from datetime import datetime, timezone
import tempfile
from pathlib import Path
import pytest

from backend.database.connection import init_db
from backend.database.repository import Repository
from backend.services.digest_service import DigestService
from backend.utils.configuration import settings


@pytest.fixture
def repo(monkeypatch):
    with tempfile.TemporaryDirectory() as tmpdir:
        test_db = Path(tmpdir) / "test_digest.db"
        monkeypatch.setattr(settings, "db_path", str(test_db))
        init_db()
        yield Repository()


def test_daily_digest_empty_db(repo):
    service = DigestService(repository=repo)
    digest = service.generate_daily_digest()

    assert digest.total_received == 0
    assert digest.high_priority_count == 0
    assert digest.cognitive_overload_level == "low"
    assert "Zero Alerts" in digest.headline


def test_daily_digest_with_notifications_and_actions(repo):
    # Insert high priority notification with action
    repo.create_notification({
        "id": "notif-dg-1",
        "event_id": "evt-dg-1",
        "package_name": "com.university.canvas",
        "title": "Assignment Deadline",
        "text": "Submit your capstone paper by tomorrow 5 PM",
        "category": "action_required",
        "category_confidence": 0.95,
        "model_type": "tfidf_logistic_regression",
        "priority_score": 88.0,
        "priority_level": "high",
        "urgency_score": 85.0,
        "action_score": 100.0,
        "deadline_score": 90.0,
        "importance_score": 75.0,
        "recency_score": 90.0,
        "action_detected": True,
        "action_type": "submit",
        "action_text": "Submit your capstone paper",
        "deadline_text": "tomorrow 5 PM",
        "deadline_at": "2026-10-25T17:00:00+00:00",
        "deadline_status": "resolved",
        "priority_reasons": ["Urgent submission due"],
        "received_at": datetime.now(timezone.utc).isoformat(),
        "processed_at": datetime.now(timezone.utc).isoformat(),
    })

    service = DigestService(repository=repo)
    digest = service.generate_daily_digest()

    assert digest.total_received == 1
    assert digest.high_priority_count == 1
    assert len(digest.actions_due_today) == 1
    assert "pending tasks detected" in digest.headline
    assert "high priority" in digest.narrative
