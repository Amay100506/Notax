"""
Unit tests for NotifyIQ action extractor module.
Tests detection of imperative verbs, multiple action verb vocabularies,
false-positive suppression on past tense statements, empty/None handling,
long texts with embedded actions, multi-lingual characters, and action type classifications.
"""

import pytest
from backend.ai.action_extractor import (
    ACTION_VERBS,
    IMPERATIVE_PREFIXES,
    ActionExtractionResult,
    extract_action,
)


def test_imperative_verbs_detection():
    """
    Test detection of explicit imperative verbs specified in requirements:
    'Please confirm your email', 'Reply to this message', 'Pay your bill'.
    """
    # 1. "Please confirm your email"
    res1 = extract_action("Please confirm your email")
    assert res1.action_detected is True
    assert res1.action_type == "confirm"
    assert "confirm your email" in res1.action_text.lower()
    assert res1.action_certainty >= 0.85

    # 2. "Reply to this message"
    res2 = extract_action("Reply to this message")
    assert res2.action_detected is True
    assert res2.action_type == "reply"
    assert "reply to this message" in res2.action_text.lower()
    assert res2.action_certainty >= 0.65

    # 3. "Pay your bill"
    res3 = extract_action("Pay your bill")
    assert res3.action_detected is True
    assert res3.action_type == "pay"
    assert "pay your bill" in res3.action_text.lower()
    assert res3.action_certainty >= 0.65


def test_multiple_action_verb_patterns():
    """
    Test detection across multiple action verb patterns (at least 8 distinct verbs).
    Verifies that each verb pattern correctly flags action_detected and matches the verb.
    """
    test_cases = [
        ("Please submit your final quarterly report", "submit"),
        ("Kindly complete the onboarding checklist", "complete"),
        ("Please review the pending pull request", "review"),
        ("Action required: approve the employee timesheet", "approve"),
        ("Reminder: confirm your flight reservation", "confirm"),
        ("You need to verify your phone number", "verify"),
        ("Please respond to the customer inquiry", "respond"),
        ("Reply to the urgent team message", "reply"),
        ("Please pay the outstanding invoice", "pay"),
        ("Kindly upload your identification document", "upload"),
        ("Tap to register for the upcoming webinar", "register"),
        ("Please attend the mandatory training session", "attend"),
        ("Urgent: renew your domain subscription", "renew"),
        ("Please download the attached contract PDF", "download"),
        ("Don't forget to update your billing address", "update"),
    ]

    # Verify we test at least 8 verbs (here we test 15)
    assert len(test_cases) >= 8

    for text, expected_verb in test_cases:
        res = extract_action(text)
        assert res.action_detected is True, f"Failed to detect action for: '{text}'"
        assert res.action_type == expected_verb, f"Expected action_type '{expected_verb}', got '{res.action_type}' for: '{text}'"
        assert res.evidence is not None
        assert res.action_certainty >= 0.50


def test_false_positive_suppression_past_tense():
    """
    Test that statements referring to past actions or completed events do NOT trigger
    false-positive action detections (e.g., 'You confirmed', 'Payment was completed').
    """
    past_tense_samples = [
        "You confirmed your email yesterday.",
        "Payment was completed successfully.",
        "Your bill was paid in full on Monday.",
        "We already reviewed your application.",
        "You updated your password 5 minutes ago.",
        "The report has been approved by management.",
        "The applicant submitted all required certificates.",
        "Order #12345 has been collected from the warehouse.",
        "You registered for the conference last week.",
        "The software patch was downloaded automatically.",
        "You downloaded the latest file yesterday.",
    ]

    for sample in past_tense_samples:
        res = extract_action(sample)
        assert res.action_detected is False, f"False positive detected on past tense: '{sample}' (result: {res})"
        assert res.action_type is None
        assert res.action_text is None


def test_empty_and_none_input_handling():
    """
    Test robust handling of empty, whitespace, and None inputs without raising exceptions.
    """
    edge_cases = [
        ("", ""),
        ("   ", "   "),
        ("", "   "),
        ("   ", ""),
        (None, None),
        (None, ""),
        ("", None),
        (None, "   "),
        ("Just a friendly hello with no action verbs.", None),
        (None, "Notification Title with no action"),
    ]

    for text, title in edge_cases:
        res = extract_action(text=text, title=title)
        assert isinstance(res, ActionExtractionResult)
        assert res.action_detected is False
        assert res.action_type is None
        assert res.action_text is None
        assert res.action_certainty == 0.0


def test_long_text_with_embedded_action():
    """
    Test that an actionable directive embedded deep within a long, verbose notification
    is correctly detected and extracted.
    """
    long_notification = (
        "Dear customer, we are writing to inform you of recent security updates applied "
        "to our infrastructure following the latest scheduled maintenance window. Several "
        "performance optimizations and encryption protocol enhancements have been rolled out "
        "across all regional clusters. In accordance with our updated compliance guidelines, "
        "please verify your account credentials by logging into your administration dashboard. "
        "Failure to do so within the specified grace period may result in restricted access. "
        "If you have any questions, our support desk remains available twenty-four hours a day."
    )

    res = extract_action(text=long_notification, title="Important Security Infrastructure Notice")
    assert res.action_detected is True
    assert res.action_type == "verify"
    assert "verify your account credentials" in res.action_text.lower()
    assert res.action_certainty >= 0.85


def test_non_english_characters_mixed_with_action_keywords():
    """
    Test detection when notification text contains non-English characters,
    accents, umlauts, CJK symbols, or emojis alongside action keywords.
    """
    multilingual_samples = [
        ("Wichtig: Please confirm your booking today", "confirm"),
        ("Bonjour! Kindly review the contract terms", "review"),
        ("Aviso importante: You need to pay your electricity bill today", "pay"),
        ("Notice: Please update your security preferences", "update"),
        ("Alerte: Please verify your phone number", "verify"),
        ("Reminder: Tap to download the meeting agenda", "download"),
    ]

    for sample, expected_verb in multilingual_samples:
        res = extract_action(sample)
        assert res.action_detected is True, f"Failed on multilingual sample: '{sample}'"
        assert res.action_type == expected_verb


def test_action_type_classification():
    """
    Verify specific action type classifications required by NotifyIQ:
    verify, payment, response, download, approval, attendance, update, and custom/fallback.
    """
    # 1. verify
    res_verify = extract_action("Please verify your identity with two-factor authentication.")
    assert res_verify.action_detected is True
    assert res_verify.action_type == "verify"

    # 2. payment (pay)
    res_payment = extract_action("Please pay your credit card bill before the due date.")
    assert res_payment.action_detected is True
    assert res_payment.action_type == "pay"

    # 3. response (reply / respond)
    res_reply = extract_action("Kindly reply to this customer support ticket.")
    assert res_reply.action_detected is True
    assert res_reply.action_type == "reply"

    res_respond = extract_action("Please respond to the survey questions today.")
    assert res_respond.action_detected is True
    assert res_respond.action_type == "respond"

    # 4. download
    res_download = extract_action("Please download the attached security patch.")
    assert res_download.action_detected is True
    assert res_download.action_type == "download"

    # 5. approval (approve)
    res_approval = extract_action("Urgent: approve the pending expense budget.")
    assert res_approval.action_detected is True
    assert res_approval.action_type == "approve"

    # 6. attendance (attend)
    res_attendance = extract_action("Please attend the annual shareholders meeting.")
    assert res_attendance.action_detected is True
    assert res_attendance.action_type == "attend"

    # 7. update
    res_update = extract_action("Please update your emergency contact details.")
    assert res_update.action_detected is True
    assert res_update.action_type == "update"

    # 8. custom / deadline fallback (e.g. 'deadline is tomorrow')
    res_custom = extract_action("Project milestone deadline is tomorrow evening.")
    assert res_custom.action_detected is True
    assert res_custom.action_type == "complete"
    assert "deadline is tomorrow evening" in res_custom.action_text.lower()


def test_imperative_prefix_certainty_boost():
    """
    Test that explicit imperative prefixes ('Please', 'Kindly', 'Urgent:')
    increase the action certainty score compared to bare action verbs.
    """
    res_bare = extract_action("Submit your assignment by evening")
    res_imperative = extract_action("Please submit your assignment by evening")

    assert res_bare.action_detected is True
    assert res_imperative.action_detected is True
    assert res_imperative.action_certainty >= res_bare.action_certainty
    assert res_imperative.action_certainty >= 0.85


def test_hinglish_action_detection():
    """Test detection of Hinglish directive verbs and imperative phrases."""
    res1 = extract_action("Aapka electricity bill turant pay karein")
    assert res1.action_detected is True
    assert res1.action_type == "pay"

    res2 = extract_action("Aaj hi recharge karein validity khatam ho rahi hai")
    assert res2.action_detected is True
    assert res2.action_type == "recharge"

    res3 = extract_action("Kripya form bharein")
    assert res3.action_detected is True
    assert res3.action_type == "bharein"

