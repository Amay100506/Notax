"""
Unit tests for end-to-end AI Pipeline execution.
"""

import tempfile
from pathlib import Path
from backend.ai.pipeline import AIPipeline
from backend.database.connection import init_db
from backend.database.repository import Repository


def test_pipeline_end_to_end_processing():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
        db_path = Path(tmpdir) / "test_pipe.db"
        init_db(db_path)
        repo = Repository(str(db_path))
        pipeline = AIPipeline(repository=repo)

        event = {
            "event_id": "e2e-001",
            "package_name": "com.university.portal",
            "title": "Assignment Submission",
            "text": "Please submit your Machine Learning final project before tomorrow 5 PM.",
            "posted_at": "2026-10-19T10:00:00+05:30",
        }

        result = pipeline.process_notification(event, persist=True)

        assert result is not None
        assert result["event_id"] == "e2e-001"
        assert result["category"] == "action_required"
        assert result["action_detected"] is True
        assert result["action_type"] == "submit"
        assert result["deadline_status"] == "resolved"
        assert "2026-10-20" in result["deadline_at"]
        assert result["priority_level"] == "high"
        assert result["priority_score"] >= 70.0
        assert len(result["priority_reasons"]) > 0

        # Verify persisted in SQLite
        persisted = repo.get_notification_by_event_id("e2e-001")
        assert persisted is not None
        assert persisted["title"] == "Assignment Submission"

        # Verify action item created
        actions = repo.list_actions()
        assert len(actions) == 1
        assert "submit" in actions[0]["action_type"].lower()
