"""
Integration tests for FastAPI endpoints using TestClient.
"""

import pytest
from fastapi.testclient import TestClient
from backend.main import app


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


def test_health_endpoint(client):
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "model_loaded" in data
    assert data["version"] == "1.0.0"


def test_process_notification_endpoint(client):
    import uuid
    test_id = f"api-test-{uuid.uuid4()}"
    payload = {
        "notification": {
            "schema_version": 1,
            "event_id": test_id,
            "package_name": "com.work.app",
            "title": "Review Document",
            "text": "Please review and approve the report before 4 PM today",
            "posted_at": "2026-10-19T10:00:00Z",
            "event_type": "posted",
        },
        "persist": True,
    }
    response = client.post("/notifications/process", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["event_id"] == test_id
    assert data["action_detected"] is True
    assert data["priority_score"] >= 70.0
    assert data["priority_level"] == "high"
    assert len(data["priority_reasons"]) > 0


def test_list_notifications_endpoint(client):
    response = client.get("/notifications?limit=10")
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert "total_count" in data
    assert isinstance(data["items"], list)


def test_analytics_summary_endpoint(client):
    response = client.get("/analytics/summary")
    assert response.status_code == 200
    data = response.json()
    assert "total_notifications" in data
    assert "high_priority" in data
    assert "action_required" in data


def test_feedback_endpoint(client):
    # Retrieve a notification id first
    list_res = client.get("/notifications?limit=1")
    items = list_res.json()["items"]
    if items:
        notif_id = items[0]["id"]
        fb_payload = {
            "notification_id": notif_id,
            "feedback_type": "priority_level",
            "original_value": "low",
            "corrected_value": "medium",
        }
        res = client.post("/feedback", json=fb_payload)
        assert res.status_code == 200
        fb_data = res.json()
        assert fb_data["notification_id"] == notif_id
        assert fb_data["corrected_value"] == "medium"


def test_settings_endpoints(client):
    # Get settings
    get_res = client.get("/settings")
    assert get_res.status_code == 200
    assert "confidence_threshold" in get_res.json()

    # Patch settings
    patch_res = client.patch("/settings", json={"settings": {"test_key": "test_val"}})
    assert patch_res.status_code == 200
    assert patch_res.json()["status"] == "settings_updated"


def test_retention_cleanup_endpoint(client):
    res = client.post("/retention/cleanup")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "cleanup_completed"
    assert "deleted_count" in data

