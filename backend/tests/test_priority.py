"""
Unit tests for explainable priority scoring.
Verifies the formula: P = 0.30U + 0.25A + 0.25D + 0.15I + 0.05R
and the reason explanations.
"""

from datetime import datetime, timezone
from backend.ai.priority_engine import score_priority, calculate_recency_score


def test_priority_score_calculation_high():
    now_iso = datetime.now(timezone.utc).isoformat()
    result = score_priority(
        category="action_required",
        text="Please submit your quarterly tax declaration before 5 PM",
        package_name="com.tax.secure",
        received_at_iso=now_iso,
        action_detected=True,
        action_certainty=0.9,
        deadline_detected=True,
        time_remaining_seconds=3600 * 2,  # 2 hours away
        is_overdue=False,
    )
    # High score expected (Urgent + Action + Approaching Deadline + High Importance + Fresh Recency)
    assert result.priority_score >= 70.0
    assert result.priority_level == "high"
    assert len(result.priority_reasons) >= 2
    assert any("deadline" in r.lower() for r in result.priority_reasons)
    assert any("action" in r.lower() for r in result.priority_reasons)


def test_priority_score_promotional_low():
    now_iso = datetime.now(timezone.utc).isoformat()
    result = score_priority(
        category="promotional",
        text="Big clearance sale on shoes 40% off",
        package_name="com.shopping.deals",
        received_at_iso=now_iso,
        action_detected=False,
        deadline_detected=False,
    )
    assert result.priority_score < 40.0
    assert result.priority_level == "low"
    assert any("promotional" in r.lower() or "marketing" in r.lower() for r in result.priority_reasons)


def test_recency_decay():
    now = datetime(2026, 10, 19, 12, 0, 0, tzinfo=timezone.utc)
    rec_fresh = "2026-10-19T12:00:00+00:00"
    rec_old = "2026-10-18T12:00:00+00:00"  # 24 hours older

    score_fresh = calculate_recency_score(rec_fresh, reference_time=now)
    score_old = calculate_recency_score(rec_old, reference_time=now)

    assert score_fresh == 100.0
    # At tau=24 hours, score should be ~ 100 * exp(-1) ~= 36.78
    assert 35.0 <= score_old <= 38.0
