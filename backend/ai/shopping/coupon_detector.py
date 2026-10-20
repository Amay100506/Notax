"""
Coupon Detector for NotifyIQ Smart Shopping Extension.

Detects and extracts coupon codes, promo codes, and vouchers from notification text.
Associates each code with its corresponding discount offer or description.
Designed for high precision across Indian and global e-commerce platforms.
"""

import re
from typing import Optional, List, Tuple
from pydantic import BaseModel, Field


class CouponInfo(BaseModel):
    """
    Extracted coupon/promo code information from notification text.
    """
    codes: list[str] = Field(default_factory=list)
    descriptions: list[str] = Field(default_factory=list)
    has_coupon: bool = False


# Words that look like all-caps codes but are common English/promotional terms
NON_COUPON_STOPWORDS = {
    "SALE", "FREE", "FLAT", "SHOP", "SAVE", "TODAY", "HURRY", "OFFER", "ORDER",
    "DEAL", "DEALS", "CLICK", "CHECK", "ITEMS", "CART", "MORE", "BEST", "EXTRA",
    "CASH", "BACK", "CARD", "BANK", "AXIS", "HDFC", "ICICI", "CREDIT", "DEBIT",
    "AMAZON", "FLIPKART", "MYNTRA", "SWIGGY", "ZOMATO", "PHONEPE", "PAYTM", "JUST",
    "ONLY", "DAYS", "YEAR", "WEEK", "ALERT", "UPDATE", "SUPER", "MEGA", "GREAT",
    "INDIAN", "PRIME", "DIWALI", "HOLI", "BILLION", "ORDERS", "LIMITED", "EXPIRES",
    "VALID", "DISCOUNT", "CASHBACK", "NOTIFICATION", "BUYNOW", "SHOPNOW", "TAPNOW",
    "APPLY", "ENTER", "CODE", "COUPON", "VOUCHER", "PROMO", "PROMOCODE", "COUPONCODE",
    "WITH", "YOUR", "HAVE", "FROM", "OVER", "UNDER", "ABOVE", "BELOW", "INR", "USD",
    "EUR", "OTP", "SMS", "COD", "EMI", "HERE", "NOW", "INFO", "FAST", "PLUS", "USER",
    "THIS", "THAT", "THEM", "THEIR", "WHAT", "WHEN", "WHERE", "WHICH", "WILL", "LOOK",
    "EXCLUSIVE", "SPECIAL", "PRICE", "PRICES", "WORTH", "FLASHSALE", "FLATOFF",
}

# Regex triggers for explicit coupon mentions: "Use code SAVE20", "Apply coupon: FLAT500", "Code: NEWUSER"
EXPLICIT_COUPON_PATTERNS = [
    # "Use code SAVE20", "apply coupon FLAT500", "Use voucher WELCOME"
    re.compile(
        r'(?i)\b(?:use|apply|enter|with|tap\s+to\s+apply|avail\s+with)\s+'
        r'(?:code|coupon|promo|voucher|promocode|coupon\s*code|promo\s*code)?'
        r'\s*[:=\-]?\s*["\'“‘]?([A-Za-z0-9]{4,15})["\'”’]?'
    ),
    # "Coupon code: FLAT500", "Promo code: SAVE20", "Voucher code: TRYNEW"
    re.compile(
        r'(?i)\b(?:coupon|promo|voucher|promocode|couponcode)\s*code'
        r'\s*[:=\-]?\s*["\'“‘]?([A-Za-z0-9]{4,15})["\'”’]?'
    ),
    # "Code: NEWUSER", "Coupon: SAVE50", "Promo: EXTRA10", "Voucher: FESTIVE"
    re.compile(
        r'(?i)\b(?:code|coupon|promo|voucher)\s*[:=\-]\s*["\'“‘]?([A-Za-z0-9]{4,15})["\'”’]?'
    ),
    # "Code SAVE20", "Coupon FLAT500"
    re.compile(
        r'(?i)\b(?:code|coupon|voucher|promo)\s+["\'“‘]?([A-Za-z0-9]{4,15})["\'”’]?'
    ),
]

# Standalone alphanumeric coupon pattern: e.g. SAVE20, FLAT500, TRYNEW10, EXTRA10, WELCOME50
ALPHANUMERIC_COUPON_PATTERN = re.compile(
    r'\b([A-Z]{2,10}\d{1,4}[A-Z0-9]*|\d{1,4}[A-Z]{2,10})\b'
)


def _is_valid_code(code: str) -> bool:
    """Validates coupon code constraints."""
    if not code:
        return False
    clean = code.strip().upper()
    # Length between 4 and 15 chars
    if not (4 <= len(clean) <= 15):
        return False
    # Must contain only alphanumeric characters
    if not clean.isalnum():
        return False
    # Must contain at least one letter (cannot be all numbers like 12345 or 2024)
    if not any(c.isalpha() for c in clean):
        return False
    # Check stop words
    if clean in NON_COUPON_STOPWORDS:
        return False
    return True


def _extract_description_for_code(code: str, text: str) -> str:
    """
    Extracts the discount offer description associated with a specific coupon code.
    """
    code_escaped = re.escape(code)

    # 1. Hyphen or colon separator right after code: "Code: NEWUSER - 50% discount on first order"
    m_sep = re.search(
        rf'(?i){code_escaped}\s*[-–:]\s*([^.!\n]+)',
        text
    )
    if m_sep:
        desc = m_sep.group(1).strip()
        if len(desc) >= 5:
            return desc.strip(" ,.-:;").capitalize()

    # 2. Connecting preposition after code: "Use code SAVE20 for flat 20% off on your first order"
    m_prep = re.search(
        rf'(?i){code_escaped}\s+(?:to\s+get|for|and\s+get|and\s+save|to\s+avail|and\s+avail|to\s+enjoy)\s+([^.!\n]+)',
        text
    )
    if m_prep:
        desc = m_prep.group(1).strip()
        if len(desc) >= 5:
            return desc.strip(" ,.-:;").capitalize()

    # 3. Discount clause before code: "Get 50% discount on first order with code NEWUSER"
    m_before = re.search(
        rf'(?i)(?:get\s+)?([^.!\n]+?(?:%\s*off|%\s*discount|discount|cashback|flat\s+[₹$]?[0-9]+))[^.!\n]*?(?:with|using|code|coupon)\s+{code_escaped}',
        text
    )
    if m_before:
        desc = m_before.group(1).strip()
        if len(desc) >= 5:
            return desc.strip(" ,.-:;").capitalize()

    # 4. Search within the same sentence as the code for discount phrases
    sentences = re.split(r'[.!\n]+', text)
    for sent in sentences:
        if re.search(rf'(?i)\b{code_escaped}\b', sent):
            # Find discount phrase in sentence
            m_disc = re.search(
                r'(?i)\b(?:\d+%\s*(?:off|discount|cashback)|flat\s+(?:₹|\$|rs\.?|inr)?\s*\d+(?:\s*off)?|(?:₹|\$|rs\.?|inr)\s*\d+\s*off|up\s*to\s*\d+%\s*off)\b[^.!\n]*',
                sent
            )
            if m_disc:
                return m_disc.group(0).strip(" ,.-:;").capitalize()
            # If the sentence itself is concise, use the sentence
            clean_sent = sent.strip(" ,.-:;")
            if 10 <= len(clean_sent) <= 80:
                return clean_sent.capitalize()

    return f"Special discount with code {code}"


def extract_coupons(text: str, title: str = "") -> CouponInfo:
    """
    Extracts coupon/promo codes and their associated discount descriptions from text.

    Handles:
    - "Use code SAVE20"
    - "Apply coupon: FLAT500"
    - "Code: NEWUSER"
    - Standalone alphanumeric codes in shopping contexts (SAVE20, FLAT500, TRYNEW10)
    - Code discount descriptions and benefits

    Returns:
        CouponInfo Pydantic model with: codes, descriptions, has_coupon.
    """
    combined = f"{title}. {text}".strip() if title else text.strip()
    if not combined:
        return CouponInfo()

    found_codes: list[str] = []

    # 1. Search with explicit trigger patterns
    for pattern in EXPLICIT_COUPON_PATTERNS:
        for match in pattern.finditer(combined):
            raw_code = match.group(1)
            if raw_code:
                code_clean = raw_code.strip(" ,.-:;!?'\"").upper()
                if _is_valid_code(code_clean) and code_clean not in found_codes:
                    found_codes.append(code_clean)

    # 2. Search for standalone alphanumeric coupon codes if in shopping context
    is_shopping_context = bool(re.search(
        r'(?i)\b(?:off|discount|order|cart|checkout|coupon|code|promo|voucher|cashback|flat|save|deal)\b',
        combined
    ))

    if is_shopping_context:
        for match in ALPHANUMERIC_COUPON_PATTERN.finditer(combined):
            raw_code = match.group(1)
            code_clean = raw_code.strip().upper()
            if _is_valid_code(code_clean) and code_clean not in found_codes:
                found_codes.append(code_clean)

    # Extract discount descriptions for each code
    descriptions: list[str] = []
    for code in found_codes:
        desc = _extract_description_for_code(code, combined)
        descriptions.append(desc)

    return CouponInfo(
        codes=found_codes,
        descriptions=descriptions,
        has_coupon=len(found_codes) > 0,
    )


# Provide detect_coupons alias
detect_coupons = extract_coupons
