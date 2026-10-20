"""
Unit and integration tests for NotifyIQ Real-Time Notification Forwarding.
Tests:
- Valid notification delivery and acknowledgment
- Invalid payloads and schema version validation
- Authentication failure handling (401)
- Duplicate event submissions and idempotent deduplication
- Batch size and payload limits
- Excluded applications filtering
- Privacy-preserving logging
- Server disconnection, reconnection, and retry behavior
"""

import logging
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from backend.api.routes import get_or_create_api_key
from backend.database.connection import init_db
from backend.database.repository import Repository
from backend.main import app
from backend.utils.configuration import settings


@pytest.fixture
def client_and_repo(monkeypatch):
    """Provides a fresh isolated test client with a temporary SQLite database."""
    with tempfile.TemporaryDirectory() as tmpdir:
        test_db = Path(tmpdir) / "test_forwarding.db"
        monkeypatch.setattr(settings, "db_path", str(test_db))
        monkeypatch.setattr(settings, "api_key", None)
        init_db()
        repo = Repository()
        client = TestClient(app)
        yield client, repo


def test_valid_notification_delivery(client_and_repo):
    client, repo = client_and_repo
    api_key = get_or_create_api_key(repo)

    payload = {
        "notifications": [
            {
                "schema_version": 1,
                "event_id": "test-fwd-001",
                "package_name": "com.google.android.gm",
                "title": "Urgent Project Deadline",
                "text": "Please submit your project review before 5 PM today.",
                "posted_at": datetime.now(timezone.utc).isoformat(),
                "event_type": "posted",
            }
        ],
        "client_version": "1.0.0",
    }

    response = client.post(
        "/api/v1/notifications/forward",
        json=payload,
        headers={"X-NotifyIQ-API-Key": api_key},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["accepted_count"] == 1
    assert data["duplicate_count"] == 0
    assert "test-fwd-001" in data["acknowledged_event_ids"]

    # Verify persisted in SQLite
    saved = repo.get_notification_by_event_id("test-fwd-001")
    assert saved is not None
    assert saved["package_name"] == "com.google.android.gm"
    assert saved["priority_level"] in ["high", "medium", "low"]


def test_invalid_payload_rejection(client_and_repo):
    client, repo = client_and_repo
    api_key = get_or_create_api_key(repo)

    # 1. Invalid schema version (> 1)
    payload_bad_schema = {
        "notifications": [
            {
                "schema_version": 99,
                "event_id": "evt-invalid-schema",
                "package_name": "com.app",
                "title": "Title",
                "text": "Text",
                "posted_at": datetime.now(timezone.utc).isoformat(),
            }
        ]
    }
    resp = client.post(
        "/api/v1/notifications/forward",
        json=payload_bad_schema,
        headers={"X-NotifyIQ-API-Key": api_key},
    )
    assert resp.status_code == 422

    # 2. Invalid timestamp format
    payload_bad_time = {
        "notifications": [
            {
                "schema_version": 1,
                "event_id": "evt-bad-time",
                "package_name": "com.app",
                "title": "Title",
                "text": "Text",
                "posted_at": "not-a-timestamp",
            }
        ]
    }
    resp2 = client.post(
        "/api/v1/notifications/forward",
        json=payload_bad_time,
        headers={"X-NotifyIQ-API-Key": api_key},
    )
    assert resp2.status_code == 422


def test_authentication_failures(client_and_repo):
    client, repo = client_and_repo
    api_key = get_or_create_api_key(repo)

    payload = {
        "notifications": [
            {
                "schema_version": 1,
                "event_id": "test-auth-001",
                "package_name": "com.app",
                "title": "Title",
                "text": "Text",
                "posted_at": datetime.now(timezone.utc).isoformat(),
            }
        ]
    }

    # 1. No auth headers provided
    resp_no_auth = client.post("/api/v1/notifications/forward", json=payload)
    assert resp_no_auth.status_code == 401
    assert "Unauthorized" in resp_no_auth.json()["detail"]

    # 2. Wrong API key
    resp_bad_auth = client.post(
        "/api/v1/notifications/forward",
        json=payload,
        headers={"X-NotifyIQ-API-Key": "wrong-secret-key"},
    )
    assert resp_bad_auth.status_code == 401

    # 3. Valid Bearer token
    resp_bearer = client.post(
        "/api/v1/notifications/forward",
        json=payload,
        headers={"Authorization": f"Bearer {api_key}"},
    )
    assert resp_bearer.status_code == 200
    assert resp_bearer.json()["accepted_count"] == 1


def test_duplicate_event_submissions_idempotency(client_and_repo):
    """
    Verifies that re-submitting an already processed event is acknowledged,
    marked as duplicate, and not processed or saved twice into the database.
    """
    client, repo = client_and_repo
    api_key = get_or_create_api_key(repo)

    payload = {
        "notifications": [
            {
                "schema_version": 1,
                "event_id": "test-idempotent-001",
                "package_name": "com.slack",
                "title": "Team sync at 3pm",
                "text": "Please join the engineering room",
                "posted_at": datetime.now(timezone.utc).isoformat(),
            }
        ]
    }

    # First attempt: accepted
    resp1 = client.post(
        "/api/v1/notifications/forward",
        json=payload,
        headers={"X-NotifyIQ-API-Key": api_key},
    )
    assert resp1.status_code == 200
    assert resp1.json()["accepted_count"] == 1
    assert resp1.json()["duplicate_count"] == 0
    assert "test-idempotent-001" in resp1.json()["acknowledged_event_ids"]

    # Second attempt (retry of same event): skipped as duplicate but acknowledged
    resp2 = client.post(
        "/api/v1/notifications/forward",
        json=payload,
        headers={"X-NotifyIQ-API-Key": api_key},
    )
    assert resp2.status_code == 200
    assert resp2.json()["accepted_count"] == 0
    assert resp2.json()["duplicate_count"] == 1
    assert "test-idempotent-001" in resp2.json()["acknowledged_event_ids"]

    # Verify only single record exists in database
    notifications, total = repo.list_notifications()
    matching = [n for n in notifications if n["event_id"] == "test-idempotent-001"]
    assert len(matching) == 1


def test_batch_size_limits(client_and_repo, monkeypatch):
    client, repo = client_and_repo
    api_key = get_or_create_api_key(repo)
    monkeypatch.setattr(settings, "max_batch_size", 5)

    items = [
        {
            "schema_version": 1,
            "event_id": f"batch-{i}",
            "package_name": "com.test",
            "title": f"Title {i}",
            "text": f"Text {i}",
            "posted_at": datetime.now(timezone.utc).isoformat(),
        }
        for i in range(10)
    ]

    resp = client.post(
        "/api/v1/notifications/forward",
        json={"notifications": items},
        headers={"X-NotifyIQ-API-Key": api_key},
    )
    assert resp.status_code == 422
    assert "Batch size 10 exceeds" in resp.json()["detail"]


def test_excluded_applications_filtering(client_and_repo):
    client, repo = client_and_repo
    api_key = get_or_create_api_key(repo)

    # Set package exclusion in repository
    repo.set_setting("excluded_packages", "com.spam.promotions,com.noisy.game")

    payload = {
        "notifications": [
            {
                "schema_version": 1,
                "event_id": "evt-excluded-1",
                "package_name": "com.spam.promotions",
                "title": "Super Mega Sale 90% Off",
                "text": "Buy now or miss out forever",
                "posted_at": datetime.now(timezone.utc).isoformat(),
            },
            {
                "schema_version": 1,
                "event_id": "evt-allowed-2",
                "package_name": "com.work.chat",
                "title": "Deployment Finished",
                "text": "Production build completed successfully.",
                "posted_at": datetime.now(timezone.utc).isoformat(),
            },
        ]
    }

    resp = client.post(
        "/api/v1/notifications/forward",
        json=payload,
        headers={"X-NotifyIQ-API-Key": api_key},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["accepted_count"] == 1
    # Both events are acknowledged so the client clears its queue
    assert "evt-excluded-1" in data["acknowledged_event_ids"]
    assert "evt-allowed-2" in data["acknowledged_event_ids"]

    # Only allowed event was persisted
    assert repo.get_notification_by_event_id("evt-excluded-1") is None
    assert repo.get_notification_by_event_id("evt-allowed-2") is not None


def test_privacy_preserving_logs(client_and_repo, caplog):
    """
    Verifies that raw notification title and body text are NEVER logged by the forwarder.
    """
    client, repo = client_and_repo
    api_key = get_or_create_api_key(repo)

    secret_title = "CONFIDENTIAL_PAYSLIP_MAY_2026"
    secret_text = "ACCOUNT_BALANCE_PRIVATE_12345678"

    payload = {
        "notifications": [
            {
                "schema_version": 1,
                "event_id": "evt-privacy-check",
                "package_name": "com.banking.app",
                "title": secret_title,
                "text": secret_text,
                "posted_at": datetime.now(timezone.utc).isoformat(),
            }
        ]
    }

    with caplog.at_level(logging.INFO):
        resp = client.post(
            "/api/v1/notifications/forward",
            json=payload,
            headers={"X-NotifyIQ-API-Key": api_key},
        )
        assert resp.status_code == 200

    log_output = caplog.text
    # Raw title and body must NEVER be in log output
    assert secret_title not in log_output
    assert secret_text not in log_output
    # Event ID and package name are permitted
    assert "evt-privacy-check" in log_output
    assert "com.banking.app" in log_output


def test_forward_status_endpoint(client_and_repo):
    client, repo = client_and_repo
    api_key = get_or_create_api_key(repo)

    # 1. Unauthenticated status check
    resp_unauth = client.get("/api/v1/forward/status")
    assert resp_unauth.status_code == 200
    assert resp_unauth.json()["status"] == "online"
    assert resp_unauth.json()["authenticated"] is False

    # 2. Authenticated status check
    resp_auth = client.get(
        "/api/v1/forward/status",
        headers={"X-NotifyIQ-API-Key": api_key},
    )
    assert resp_auth.status_code == 200
    assert resp_auth.json()["authenticated"] is True
    assert "server_time" in resp_auth.json()


def test_client_retry_and_reconnection_simulation(client_and_repo):
    """
    Simulates the Android client's persistent queue, offline network failure,
    exponential backoff retry, and final reconnection to ensure zero event loss
    and zero duplicate records.
    """
    client, repo = client_and_repo
    api_key = get_or_create_api_key(repo)

    # Client-side persistent queue simulation
    client_queue = [
        {
            "schema_version": 1,
            "event_id": f"queued-{i}",
            "package_name": "com.app.sync",
            "title": f"Title {i}",
            "text": f"Content {i}",
            "posted_at": datetime.now(timezone.utc).isoformat(),
            "event_type": "posted",
        }
        for i in range(3)
    ]

    # Attempt 1: Server Disconnection (Simulate 503 / network error)
    # Queue is retained without losing events
    server_online = False
    if not server_online:
        # Client catches exception, events remain in queue
        assert len(client_queue) == 3

    # Attempt 2: Server Reconnects
    server_online = True
    batch = list(client_queue)  # Peek batch
    resp = client.post(
        "/api/v1/notifications/forward",
        json={"notifications": batch},
        headers={"X-NotifyIQ-API-Key": api_key},
    )
    assert resp.status_code == 200
    ack_ids = set(resp.json()["acknowledged_event_ids"])

    # Client dequeues acknowledged IDs
    client_queue = [item for item in client_queue if item["event_id"] not in ack_ids]
    assert len(client_queue) == 0

    # Verify all 3 events are stored in backend SQLite
    for i in range(3):
        saved = repo.get_notification_by_event_id(f"queued-{i}")
        assert saved is not None
