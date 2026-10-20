"""
Unit tests for duplicate detection (exact and near duplicate grouping).
Covers deterministic SHA-256 fingerprinting, Level 2 TF-IDF cosine similarity,
non-duplicate isolation, and empty/whitespace text edge cases.
"""

import tempfile
from pathlib import Path
from backend.ai.duplicate_detector import DuplicateDetector
from backend.database.connection import init_db
from backend.database.repository import Repository


def test_exact_duplicate_detection():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
        db_path = Path(tmpdir) / "test_dup.db"
        init_db(db_path)
        repo = Repository(str(db_path))
        detector = DuplicateDetector(repository=repo)

        # 1. First event
        res1 = detector.check_duplicate(
            package_name="com.bank.app",
            title="Account Alert",
            text="Debited USD 20.00 at Store",
        )
        assert res1.is_duplicate is False
        assert res1.duplicate_group_id is not None

        # Seed this into repository as an ingested notification
        repo.create_notification({
            "event_id": "evt-dup-1",
            "package_name": "com.bank.app",
            "title": "Account Alert",
            "text": "Debited USD 20.00 at Store",
            "category": "transactional",
            "priority_score": 50.0,
            "duplicate_group_id": res1.duplicate_group_id,
            "is_duplicate": False,
            "received_at": "2026-10-19T10:00:00Z",
        })

        # 2. Second event with identical package, title, and text
        res2 = detector.check_duplicate(
            package_name="com.bank.app",
            title="Account Alert",
            text="Debited USD 20.00 at Store",
        )
        assert res2.is_duplicate is True
        assert res2.duplicate_group_id == res1.duplicate_group_id
        assert res2.grouping_method == "exact"


def test_near_duplicate_detection():
    """
    Test Level 2 TF-IDF cosine similarity detection for near-duplicate texts.
    Verifies that slightly rephrased notifications from the same package above the
    threshold are correctly recognized as near duplicates.
    """
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
        db_path = Path(tmpdir) / "test_near_dup.db"
        init_db(db_path)
        repo = Repository(str(db_path))
        detector = DuplicateDetector(repository=repo)

        title1 = "Flash Sale Alert!"
        text1 = (
            "Get massive discounts of 50 percent off on all electronics, accessories, "
            "laptops, and smartphones today only at our main store!"
        )

        title2 = "Flash Sale Alert!"
        text2 = (
            "Get massive discounts of 50 percent off on all electronics, accessories, "
            "laptops, and smartphones today only at our downtown store!"
        )

        # 1. First event evaluated and stored
        res1 = detector.check_duplicate(
            package_name="com.shopping.app",
            title=title1,
            text=text1,
        )
        assert res1.is_duplicate is False
        assert res1.duplicate_group_id is not None

        repo.create_notification({
            "event_id": "evt-near-1",
            "package_name": "com.shopping.app",
            "title": title1,
            "text": text1,
            "category": "promotions",
            "priority_score": 30.0,
            "duplicate_group_id": res1.duplicate_group_id,
            "is_duplicate": False,
            "received_at": "2026-10-19T10:00:00Z",
        })

        # 2. Second event with near-identical wording
        res2 = detector.check_duplicate(
            package_name="com.shopping.app",
            title=title2,
            text=text2,
        )
        assert res2.is_duplicate is True
        assert res2.grouping_method == "near_duplicate"
        assert res2.similarity_score is not None
        assert res2.similarity_score >= 0.85
        assert res2.duplicate_group_id is not None


def test_completely_different_texts():
    """
    Verify non-duplicates from the same or different packages don't get grouped together.
    """
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
        db_path = Path(tmpdir) / "test_diff.db"
        init_db(db_path)
        repo = Repository(str(db_path))
        detector = DuplicateDetector(repository=repo)

        # Seed initial security alert
        res1 = detector.check_duplicate(
            package_name="com.bank.app",
            title="Account Security Alert",
            text="New login detected from unrecognized Chrome browser on Windows.",
        )
        assert res1.is_duplicate is False

        repo.create_notification({
            "event_id": "evt-diff-1",
            "package_name": "com.bank.app",
            "title": "Account Security Alert",
            "text": "New login detected from unrecognized Chrome browser on Windows.",
            "category": "security",
            "priority_score": 85.0,
            "duplicate_group_id": res1.duplicate_group_id,
            "is_duplicate": False,
            "received_at": "2026-10-19T10:00:00Z",
        })

        # Event 2: completely different text from the same package
        res2 = detector.check_duplicate(
            package_name="com.bank.app",
            title="Monthly Statement Ready",
            text="Your checking account statement for September is now available for download.",
        )
        assert res2.is_duplicate is False
        assert res2.grouping_method == "exact_anchor"
        assert res2.duplicate_group_id != res1.duplicate_group_id

        # Event 3: completely different text from a different package
        res3 = detector.check_duplicate(
            package_name="com.airline.travel",
            title="Flight Check-in Open",
            text="Online check-in for flight AA123 to Chicago is now open. Confirm your seat.",
        )
        assert res3.is_duplicate is False
        assert res3.grouping_method == "exact_anchor"
        assert res3.duplicate_group_id != res1.duplicate_group_id
        assert res3.duplicate_group_id != res2.duplicate_group_id


def test_empty_text_fingerprinting():
    """
    Edge case tests with empty and whitespace content.
    Verifies deterministic fingerprinting and grouping for empty content.
    """
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
        db_path = Path(tmpdir) / "test_empty_dup.db"
        init_db(db_path)
        repo = Repository(str(db_path))
        detector = DuplicateDetector(repository=repo)

        # 1. Fingerprint normalization across empty and whitespace strings
        fp_empty = detector.generate_exact_fingerprint("com.test.app", "", "")
        fp_spaces = detector.generate_exact_fingerprint("com.test.app", "   ", "   \t\n")
        assert fp_empty == fp_spaces
        assert len(fp_empty) == 16

        # 2. First empty notification is not marked duplicate
        res1 = detector.check_duplicate(
            package_name="com.test.app",
            title="",
            text="",
        )
        assert res1.is_duplicate is False
        assert res1.grouping_method == "exact_anchor"
        assert res1.duplicate_group_id is not None

        repo.create_notification({
            "event_id": "evt-empty-1",
            "package_name": "com.test.app",
            "title": "",
            "text": "",
            "category": "system",
            "priority_score": 10.0,
            "duplicate_group_id": res1.duplicate_group_id,
            "is_duplicate": False,
            "received_at": "2026-10-19T10:00:00Z",
        })

        # 3. Second identical empty notification is marked duplicate
        res2 = detector.check_duplicate(
            package_name="com.test.app",
            title="",
            text="",
        )
        assert res2.is_duplicate is True
        assert res2.duplicate_group_id == res1.duplicate_group_id
        assert res2.grouping_method == "exact"

        # 4. Empty notification from a different package is not grouped
        res3 = detector.check_duplicate(
            package_name="com.other.app",
            title="",
            text="",
        )
        assert res3.is_duplicate is False
        assert res3.duplicate_group_id != res1.duplicate_group_id
