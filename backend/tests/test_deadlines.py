"""
Unit tests for deadline extractor.
Tests time expressions, relative intervals, ambiguous dates, and timezone handling.
"""

from backend.ai.deadline_extractor import extract_deadline


def test_extract_tomorrow_deadline():
    ref_time = "2026-10-19T10:00:00+05:30"
    text = "Submit the project proposal by tomorrow 5 PM."
    res = extract_deadline(text, reference_time_str=ref_time)
    assert res.deadline_detected is True
    assert res.resolution_status == "resolved"
    assert res.deadline_at is not None
    assert "2026-10-20" in res.deadline_at
    assert "17:00:00" in res.deadline_at
    assert res.time_remaining_seconds is not None
    assert res.time_remaining_seconds > 0
    assert res.is_overdue is False


def test_extract_relative_hours_deadline():
    ref_time = "2026-10-19T10:00:00+00:00"
    text = "Please verify your account within 24 hours."
    res = extract_deadline(text, reference_time_str=ref_time)
    assert res.deadline_detected is True
    assert res.resolution_status == "resolved"
    assert res.time_remaining_seconds == 24 * 3600


def test_extract_ambiguous_deadline():
    text = "Please update your profile sometime soon or by next week."
    res = extract_deadline(text)
    assert res.deadline_detected is True
    assert res.resolution_status == "unresolved"
    assert res.deadline_at is None


def test_no_deadline():
    text = "Hey, hope you are having a wonderful day!"
    res = extract_deadline(text)
    assert res.deadline_detected is False
    assert res.resolution_status == "none"
    assert res.deadline_at is None


def test_dateparser_natural_language_deadline():
    ref_time = "2026-10-20T10:00:00+05:30"
    text = "Important: registration closes on 25 October 2026. Please complete your submission."
    res = extract_deadline(text, reference_time_str=ref_time)
    assert res.deadline_detected is True
    assert res.resolution_status == "resolved"
    assert res.deadline_at is not None
    assert "2026-10-25" in res.deadline_at
