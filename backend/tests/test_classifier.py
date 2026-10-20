"""
Unit tests for CategoryClassifier.
Tests ML pipeline predictions and fallback behavior.
"""

from pathlib import Path
from backend.ai.classifier import CategoryClassifier


def test_classifier_loads_and_predicts():
    clf = CategoryClassifier()
    # Test action_required
    res = clf.predict("Please review and approve the project budget proposal before 5 PM", title="Document Approval")
    assert res.category == "action_required"
    assert res.confidence > 0.50

    # Test promotional
    res_promo = clf.predict("FLASH SALE 50% OFF! Use code SAVE50 today on all shoes", title="Big Sale")
    assert res_promo.category == "promotional"

    # Test transactional
    res_tx = clf.predict("Your package with tracking number 98124 is out for delivery", title="Order Update")
    assert res_tx.category == "transactional"


def test_classifier_rule_fallback_on_missing_model():
    # Point classifier to non-existent model
    clf = CategoryClassifier(model_path=Path("non_existent_model.joblib"))
    assert clf.model is None

    # Verify deterministic fallback works
    res = clf.predict("Please submit your final assignment", title="Homework")
    assert res.category == "action_required"
    assert res.model_type == "rule_fallback"

    res_unknown = clf.predict("XYZ 123490 qwe", title="")
    assert res_unknown.category == "unknown"
    assert res_unknown.needs_review is True
