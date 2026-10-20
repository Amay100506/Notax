"""
Unit tests for JSON import and export service.
Verifies validation rules, rejection of malformed inputs, and duplicate protection.
"""

import tempfile
from pathlib import Path
from backend.database.connection import init_db
from backend.database.repository import Repository
from backend.services.import_service import ImportService


def test_validate_valid_notification_list():
    service = ImportService()
    valid_batch = [
        {
            "schema_version": 1,
            "event_id": "evt-001",
            "package_name": "com.test.app",
            "title": "Title 1",
            "text": "Message 1",
            "posted_at": "2026-10-19T10:00:00Z",
            "event_type": "posted",
        },
        {
            "schema_version": 1,
            "event_id": "evt-002",
            "package_name": "com.test.app",
            "title": "",
            "text": "Missing title is allowed",
            "posted_at": "2026-10-19T10:05:00+05:30",
            "event_type": "posted",
        },
    ]
    report = service.validate_and_filter_events(valid_batch)
    assert report.total_records == 2
    assert report.accepted_count == 2
    assert report.rejected_count == 0


def test_reject_malformed_notifications():
    service = ImportService()
    bad_batch = [
        # Missing event_id
        {"schema_version": 1, "package_name": "com.app", "posted_at": "2026-10-19T10:00:00Z"},
        # Invalid timestamp
        {"schema_version": 1, "event_id": "e2", "package_name": "com.app", "posted_at": "not-a-date"},
        # Not a dict
        "invalid string record",
    ]
    report = service.validate_and_filter_events(bad_batch)
    assert report.total_records == 3
    assert report.accepted_count == 0
    assert report.rejected_count == 3
    assert len(report.rejected_records) == 3


def test_skip_already_processed_event():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
        db_path = Path(tmpdir) / "test_import.db"
        init_db(db_path)
        repo = Repository(str(db_path))

        # Seed one record
        repo.create_notification({
            "event_id": "existing-evt-99",
            "package_name": "com.existing.app",
            "title": "Existing",
            "category": "system",
            "priority_score": 10.0,
            "received_at": "2026-10-19T10:00:00Z",
        })

        service = ImportService(repository=repo)
        incoming = [
            {
                "schema_version": 1,
                "event_id": "existing-evt-99",
                "package_name": "com.existing.app",
                "title": "Existing",
                "posted_at": "2026-10-19T10:00:00Z",
                "event_type": "posted",
            },
            {
                "schema_version": 1,
                "event_id": "brand-new-evt-100",
                "package_name": "com.new.app",
                "title": "New Event",
                "posted_at": "2026-10-19T11:00:00Z",
                "event_type": "posted",
            },
        ]
        report = service.validate_and_filter_events(incoming)
        assert report.total_records == 2
        assert report.already_processed_count == 1
        assert report.accepted_count == 1
        assert report.accepted_records[0]["event_id"] == "brand-new-evt-100"


def test_shopping_notifications_dataset_valid():
    """Verifies that shopping_notifications.json has exactly 40 valid Indian e-commerce notifications."""
    import json
    data_path = Path(__file__).resolve().parent.parent.parent / "data" / "shopping_notifications.json"
    assert data_path.exists(), "shopping_notifications.json must exist in data directory"

    with open(data_path, "r", encoding="utf-8") as f:
        events = json.load(f)

    assert len(events) == 40

    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
        db_path = Path(tmpdir) / "test_shopping.db"
        init_db(db_path)
        repo = Repository(str(db_path))
        service = ImportService(repository=repo)

        report = service.validate_and_filter_events(events)
        assert report.total_records == 40
        assert report.accepted_count == 40
        assert report.rejected_count == 0

    # Verify app breakdown
    pkg_counts: dict[str, int] = {}
    for ev in events:
        pkg = ev["package_name"]
        pkg_counts[pkg] = pkg_counts.get(pkg, 0) + 1

    assert pkg_counts["com.amazon.mShop.android.shopping"] == 10
    assert pkg_counts["com.flipkart.android"] == 8
    assert pkg_counts["com.myntra.android"] == 5
    assert (pkg_counts.get("in.swiggy.android", 0) + pkg_counts.get("com.application.zomato", 0)) == 5
    assert (pkg_counts.get("net.one97.paytm", 0) + pkg_counts.get("com.phonepe.app", 0)) == 5
    assert (pkg_counts.get("com.ril.ajio", 0) + pkg_counts.get("com.fsn.nykaa", 0) + pkg_counts.get("com.meesho.supply", 0)) == 7


