"""
Unit and integration tests for NotifyIQ Calendar Synchronization.
Tests RFC 5545 .ics generation, Google Calendar URL encoding, Outlook web links,
and FastAPI calendar endpoints.
"""

from datetime import datetime, timezone, timedelta
import tempfile
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.database.connection import init_db
from backend.database.repository import Repository
from backend.utils.configuration import settings
from backend.utils.calendar_sync import (
    generate_ics_content,
    generate_google_calendar_url,
    generate_outlook_calendar_url,
    format_ics_datetime,
)


@pytest.fixture
def client_and_repo(monkeypatch):
    """Provides a fresh isolated test client with a temporary SQLite database."""
    with tempfile.TemporaryDirectory() as tmpdir:
        test_db = Path(tmpdir) / "test_calendar.db"
        monkeypatch.setattr(settings, "db_path", str(test_db))
        init_db()
        repo = Repository()
        client = TestClient(app)
        yield client, repo


def test_format_ics_datetime():
    dt = datetime(2026, 10, 25, 14, 30, 0, tzinfo=timezone.utc)
    res = format_ics_datetime(dt)
    assert res == "20261025T143000Z"


def test_generate_ics_content():
    deadline = datetime(2026, 10, 25, 17, 0, 0, tzinfo=timezone.utc)
    title = "Submit Final Assignment"
    desc = "Complete the quarterly report and upload to portal"

    ics = generate_ics_content(
        title=title,
        description=desc,
        deadline_at=deadline,
        event_uid="test-event-1234",
        duration_minutes=45,
    )

    assert "BEGIN:VCALENDAR" in ics
    assert "VERSION:2.0" in ics
    assert "BEGIN:VEVENT" in ics
    assert "UID:test-event-1234" in ics
    assert "SUMMARY:Submit Final Assignment" in ics
    assert "DTSTART:20261025T170000Z" in ics
    assert "DTEND:20261025T174500Z" in ics
    assert "TRIGGER:-PT15M" in ics
    assert "END:VEVENT" in ics
    assert "END:VCALENDAR" in ics


def test_generate_google_calendar_url():
    deadline = datetime(2026, 10, 25, 10, 0, 0, tzinfo=timezone.utc)
    title = "Team Sprint Planning"
    desc = "Sprint backlog grooming"

    url = generate_google_calendar_url(title=title, description=desc, deadline_at=deadline)
    assert "calendar.google.com/calendar/render" in url
    assert "action=TEMPLATE" in url
    assert "text=Team+Sprint+Planning" in url
    assert "20261025T100000Z%2F20261025T103000Z" in url


def test_generate_outlook_calendar_url():
    deadline = datetime(2026, 10, 25, 10, 0, 0, tzinfo=timezone.utc)
    title = "Doctor Appointment"
    desc = "Annual physical checkup"

    url = generate_outlook_calendar_url(title=title, description=desc, deadline_at=deadline)
    assert "outlook.live.com/calendar" in url
    assert "subject=Doctor+Appointment" in url
    assert "startdt=2026-10-25T10%3A00%3A00Z" in url


def test_api_calendar_endpoints(client_and_repo):
    client, repo = client_and_repo

    # Create a notification with an action in SQLite
    notif_data = {
        "id": "notif-cal-001",
        "event_id": "evt-cal-001",
        "package_name": "com.university.canvas",
        "title": "Assignment Deadline Notice",
        "text": "Submit your assignment by tomorrow at 5 PM",
        "category": "action_required",
        "category_confidence": 0.95,
        "model_type": "tfidf_logistic_regression",
        "priority_score": 85.0,
        "priority_level": "high",
        "urgency_score": 80.0,
        "action_score": 100.0,
        "deadline_score": 90.0,
        "importance_score": 70.0,
        "recency_score": 95.0,
        "action_detected": True,
        "action_type": "submit",
        "action_text": "Submit your assignment",
        "deadline_text": "tomorrow at 5 PM",
        "deadline_at": "2026-10-25T17:00:00+00:00",
        "deadline_status": "resolved",
        "priority_reasons": ["Urgent assignment deadline"],
        "received_at": "2026-10-24T10:00:00+00:00",
        "processed_at": "2026-10-24T10:00:05+00:00",
        "actions": [
            {
                "id": "act-cal-001",
                "action_type": "submit",
                "action_text": "Submit your assignment",
                "deadline_phrase": "tomorrow at 5 PM",
                "deadline_at": "2026-10-25T17:00:00+00:00",
                "deadline_confidence": 0.9,
                "status": "open",
            }
        ],
    }

    repo.create_notification(notif_data)
    actions = repo.list_actions()
    assert len(actions) > 0
    action_id = actions[0]["id"]

    # 1. Test .ics download endpoint
    resp_ics = client.get(f"/api/v1/actions/{action_id}/calendar.ics")
    assert resp_ics.status_code == 200
    assert "text/calendar" in resp_ics.headers.get("content-type", "")
    assert "attachment" in resp_ics.headers.get("content-disposition", "")
    assert "BEGIN:VCALENDAR" in resp_ics.text
    assert "Submit your assignment" in resp_ics.text

    # 2. Test calendar web links endpoint
    resp_links = client.get(f"/api/v1/actions/{action_id}/calendar-links")
    assert resp_links.status_code == 200
    data = resp_links.json()
    assert data["action_id"] == action_id
    assert "calendar.google.com" in data["google_calendar_url"]
    assert "outlook.live.com" in data["outlook_calendar_url"]
    assert data["ics_download_url"] == f"/api/v1/actions/{action_id}/calendar.ics"

    # 3. Test non-existent action ID returns 404
    resp_404 = client.get("/api/v1/actions/nonexistent-id/calendar.ics")
    assert resp_404.status_code == 404
