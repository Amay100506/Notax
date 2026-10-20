"""
Unit tests for text preprocessing, Unicode normalization, and redaction.
"""

from backend.ai.preprocess import preprocess_text, redact_sensitive_patterns, normalize_unicode


def test_unicode_and_whitespace_normalization():
    raw = "  Hello \u00A0 \t World!  \n\n  How are   you?  "
    res = preprocess_text(raw)
    assert res.original_text == "Hello World! How are you?"
    assert res.normalized_text == "hello world! how are you?"


def test_redact_email_phone_url():
    raw = "Contact support@example.com or visit https://secure.portal.com or call 555-123-4567"
    redacted, was_redacted = redact_sensitive_patterns(raw)
    assert was_redacted is True
    assert "[EMAIL]" in redacted
    assert "[URL]" in redacted
    assert "[PHONE]" in redacted
    assert "support@example.com" not in redacted
    assert "https://secure.portal.com" not in redacted
    assert "555-123-4567" not in redacted


def test_redact_account_and_otp():
    raw = "Your card 4532 8912 3456 7890 was charged. Verification code is 948210"
    redacted, was_redacted = redact_sensitive_patterns(raw)
    assert was_redacted is True
    assert "[ACCOUNT]" in redacted
    assert "[CODE]" in redacted
    assert "948210" not in redacted


def test_empty_and_none_text():
    res1 = preprocess_text("")
    assert res1.original_text == ""
    assert res1.normalized_text == ""

    res2 = preprocess_text(None)
    assert res2.original_text == ""
    assert res2.normalized_text == ""


def test_length_limit_enforced():
    long_str = "a" * 1500
    res = preprocess_text(long_str, max_length=100)
    assert len(res.original_text) == 100
