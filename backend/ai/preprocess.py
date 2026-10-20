"""
Text preprocessing and privacy-conscious redaction for NotifyIQ.
Handles Unicode normalization, whitespace cleanup, length limits,
and masking of sensitive identifiers (emails, phones, accounts, URLs, OTPs).
"""

import re
import unicodedata
from typing import NamedTuple

# Regex patterns for sensitive data redaction
RE_EMAIL = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
RE_URL = re.compile(r"https?://\S+|www\.\S+")
RE_PHONE = re.compile(r"(?:\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b")
RE_ACCOUNT_CARD = re.compile(r"\b(?:\d[ -]*?){13,19}\b")
RE_OTP = re.compile(r"\b(?:otp|code|pin|verification)\s*(?:is|:)?\s*([0-9]{4,8})\b", re.IGNORECASE)


class PreprocessResult(NamedTuple):
    original_text: str
    normalized_text: str
    redacted_text: str
    was_redacted: bool
    length: int


def normalize_unicode(text: str) -> str:
    """Normalizes Unicode characters to NFKC standard form."""
    if not text:
        return ""
    return unicodedata.normalize("NFKC", str(text))


def clean_whitespace(text: str) -> str:
    """Replaces consecutive whitespace, newlines, and tabs with a single space."""
    if not text:
        return ""
    return " ".join(text.strip().split())


def redact_sensitive_patterns(text: str) -> tuple[str, bool]:
    """
    Masks common sensitive patterns with placeholder tokens.
    Returns (redacted_text, was_redacted_bool).
    Note: Redaction is rule-based pattern matching and should not be treated
    as complete anonymization.
    """
    if not text:
        return "", False

    original = text
    # 1. Mask URLs
    redacted = RE_URL.sub("[URL]", original)
    # 2. Mask Emails
    redacted = RE_EMAIL.sub("[EMAIL]", redacted)
    # 3. Mask Credit Cards / Account numbers
    redacted = RE_ACCOUNT_CARD.sub("[ACCOUNT]", redacted)
    # 4. Mask Phone numbers
    redacted = RE_PHONE.sub("[PHONE]", redacted)
    # 5. Mask OTP codes
    redacted = RE_OTP.sub(r"code [CODE]", redacted)

    was_redacted = redacted != original
    return redacted, was_redacted


def preprocess_text(
    text: str | None,
    apply_redaction: bool = True,
    max_length: int = 1000,
) -> PreprocessResult:
    """
    Main preprocessing pipeline for notification title or body.
    Produces safe original text, normalized classification text, and redacted text.
    """
    if text is None:
        text = ""

    # Step 1: Unicode & Whitespace Normalization
    cleaned = clean_whitespace(normalize_unicode(text))

    # Step 2: Enforce max length
    if len(cleaned) > max_length:
        cleaned = cleaned[:max_length]

    # Step 3: Redaction if enabled
    redacted, was_redacted = redact_sensitive_patterns(cleaned) if apply_redaction else (cleaned, False)

    # Step 4: Classification Normalization (lowercase, strip extra punct for vectorizer)
    normalized = redacted.lower()

    return PreprocessResult(
        original_text=cleaned,
        normalized_text=normalized,
        redacted_text=redacted,
        was_redacted=was_redacted,
        length=len(cleaned),
    )


def safe_tokenize(text: str) -> list[str]:
    """Simple alphanumeric tokenization for rule-based analysis."""
    if not text:
        return []
    return re.findall(r"\b\w+\b", text.lower())
