"""
Price Extractor for NotifyIQ Smart Shopping Extension.

Extracts monetary prices and discount percentages from e-commerce notifications.
Handles Indian Rupee (₹, Rs, INR) and US Dollar ($ , USD) currencies, multiple price
comparisons (original vs discounted / MRP vs deal price), and contextual percentages.
"""

import re
from typing import Optional, List, Tuple
from pydantic import BaseModel, Field


class PriceInfo(BaseModel):
    """
    Structured price and discount information extracted from notification text.
    """
    original_price: Optional[float] = None
    discounted_price: Optional[float] = None
    currency: Optional[str] = None
    discount_percent: Optional[float] = None
    price_texts_found: list[str] = Field(default_factory=list)

    @property
    def savings(self) -> Optional[float]:
        """Calculates absolute monetary savings if both prices are available."""
        if self.original_price is not None and self.discounted_price is not None:
            if self.original_price >= self.discounted_price:
                return round(self.original_price - self.discounted_price, 2)
        return None


# Prefix currency regex: ₹1,299, Rs. 1299, Rs 499, INR 1,299.00, $29.99, USD 15.00, Rs.499
PREFIX_PRICE_PATTERN = re.compile(
    r'(?i)(?P<sym>(?<=\b)(?:rs|inr|re|usd)\.?|₹|\$)\s*'
    r'(?P<amount>\d+(?:,\d+)*(?:\.\d+)?)(?:\s*/-)?'
)

# Suffix currency regex: 1299 Rs, 499/-, 1,299/- INR, 29.99 USD, 1299 rupees
SUFFIX_PRICE_PATTERN = re.compile(
    r'(?i)(?:^|[^\w])(?P<amount>\d+(?:,\d+)*(?:\.\d+)?)'
    r'\s*(?:/-\s*(?P<slash_sym>inr|rs\.?|rupees)?|(?P<sym>\b(?:inr|rs\.?|rupees|usd|dollars)\b)|/-)'
)

# Context markers for identifying original vs discounted prices
ORIGINAL_INDICATORS = [
    r'\bmrp\b',
    r'\bwas\b',
    r'\boriginal(?:ly)?\b',
    r'\bregular\b',
    r'\bworth\b',
    r'\blist\s*price\b',
    r'\bretail\b',
    r'\bactual\b',
    r'\bfrom\b',
    r'\bbefore\b',
    r'\bstrikethrough\b',
    r'\binstead\s+of\b',
    r'~~',
]

DISCOUNTED_INDICATORS = [
    r'\bnow\b',
    r'\bat\b',
    r'\bdeal\s*price\b',
    r'\boffer\s*price\b',
    r'\bspecial\s*price\b',
    r'\bpay\s*(?:only)?\b',
    r'\beffective\s*price\b',
    r'\bjust\b',
    r'\bonly\b',
    r'\bgrab\s*at\b',
    r'\bbuy\s*at\b',
    r'\bfor\b',
    r'\bloot\s*price\b',
    r'\bstarting\s*(?:at|from)?\b',
    r'\bdown\s*to\b',
    r'\breduced\s*to\b',
    r'\bgrab\s*for\b',
    r'\bget\s*at\b',
]

# Patterns for percentage discounts: 50% off, flat 30% discount, upto 60% off, save 25%
DISCOUNT_PERCENT_PATTERNS = [
    re.compile(r'(?i)\b(?:flat|upto|up\s*to|extra|save|discount\s+of)\s+(\d{1,2}(?:\.\d{1,2})?)\s*%\s*(?:off|discount|cashback)?'),
    re.compile(r'(?i)\b(\d{1,2}(?:\.\d{1,2})?)\s*%\s*(?:off|discount|cashback|cash\s*back|save|savings|less)\b'),
    re.compile(r'(?i)\b(?:flat|upto|up\s*to|extra)\s+(\d{1,2}(?:\.\d{1,2})?)\s*%'),
    re.compile(r'(?i)\b(\d{1,2}(?:\.\d{1,2})?)\s*%\b'),
]


def _clean_amount(raw_val: str) -> Optional[float]:
    """Converts a comma-separated or integer string into a clean float."""
    try:
        clean = raw_val.replace(',', '').strip()
        val = float(clean)
        return val if val >= 0 else None
    except (ValueError, TypeError):
        return None


def _normalize_currency(sym_str: str) -> Optional[str]:
    """Maps raw currency symbols and abbreviations to standard currency codes."""
    if not sym_str:
        return None
    s = sym_str.lower().strip().replace('.', '')
    if s in {'₹', 'rs', 'inr', 're', 'rupees'}:
        return "INR"
    if s in {'$', 'usd', 'dollars'}:
        return "USD"
    return None


def _extract_discount_percent(text: str) -> Optional[float]:
    """Detects and parses percentage discount values from text."""
    for pattern in DISCOUNT_PERCENT_PATTERNS:
        match = pattern.search(text)
        if match:
            try:
                pct = float(match.group(1))
                if 0 < pct <= 100:
                    return pct
            except (ValueError, IndexError):
                continue
    return None


def _check_context_window(text: str, start: int, end: int) -> Tuple[bool, bool]:
    """
    Inspects surrounding context (35 chars before, 20 chars after)
    to classify price as original vs discounted.
    """
    pre_window = text[max(0, start - 35):start].lower()
    post_window = text[end:min(len(text), end + 20)].lower()
    combined_window = f"{pre_window} {post_window}"

    is_orig = any(re.search(pat, combined_window) for pat in ORIGINAL_INDICATORS)
    is_disc = any(re.search(pat, combined_window) for pat in DISCOUNTED_INDICATORS)

    return is_orig, is_disc


def extract_prices(text: str, title: str = "") -> PriceInfo:
    """
    Extracts prices, currency, and discounts from notification title and body text.

    Handles:
    - Indian Rupee: ₹1,299, Rs. 1299, INR 1,299.00, Rs 499, 499/-
    - US Dollar: $29.99, USD 15.00
    - Multi-price notifications (MRP vs Deal Price, was vs now)
    - Percentage discounts: 50% off, flat 30% discount
    - Missing price resolution using detected discount percentage

    Returns:
        PriceInfo Pydantic model with structured price data.
    """
    combined = f"{title}. {text}".strip() if title else text.strip()
    if not combined:
        return PriceInfo()

    found_matches: List[dict] = []
    matched_spans: List[Tuple[int, int]] = []

    # 1. Search for prefix prices (e.g. ₹1,299, Rs. 1299, $29.99)
    for m in PREFIX_PRICE_PATTERN.finditer(combined):
        span = m.span()
        amount = _clean_amount(m.group("amount"))
        if amount is not None:
            raw_sym = m.group("sym")
            curr = _normalize_currency(raw_sym)
            raw_text = m.group(0).strip()
            is_orig, is_disc = _check_context_window(combined, span[0], span[1])
            found_matches.append({
                "amount": amount,
                "currency": curr,
                "raw_text": raw_text,
                "span": span,
                "is_orig": is_orig,
                "is_disc": is_disc,
            })
            matched_spans.append(span)

    # 2. Search for suffix prices (e.g. 1299 Rs, 499/-, 15.00 USD)
    for m in SUFFIX_PRICE_PATTERN.finditer(combined):
        span = m.span()
        # Avoid overlapping matches from prefix pattern
        if any(not (span[1] <= s[0] or span[0] >= s[1]) for s in matched_spans):
            continue

        amount = _clean_amount(m.group("amount"))
        if amount is not None:
            raw_sym = m.group("slash_sym") or m.group("sym") or "₹"
            curr = _normalize_currency(raw_sym) or "INR"
            raw_text = m.group(0).strip()
            is_orig, is_disc = _check_context_window(combined, span[0], span[1])
            found_matches.append({
                "amount": amount,
                "currency": curr,
                "raw_text": raw_text,
                "span": span,
                "is_orig": is_orig,
                "is_disc": is_disc,
            })
            matched_spans.append(span)

    # Extract discount percent from full text
    explicit_discount_pct = _extract_discount_percent(combined)

    # Compile raw price texts found preserving occurrence order
    price_texts_found = [m["raw_text"] for m in found_matches]

    # Resolve currency: pick from matches or fallback to INR/USD if mentioned
    currency: Optional[str] = None
    for m in found_matches:
        if m["currency"]:
            currency = m["currency"]
            break
    if not currency:
        if re.search(r'(?i)₹|\brs\.?|\binr\b', combined):
            currency = "INR"
        elif re.search(r'(?i)\$|\busd\b', combined):
            currency = "USD"

    # Price assignment logic
    original_price: Optional[float] = None
    discounted_price: Optional[float] = None

    if len(found_matches) >= 2:
        # Separate by explicit context tags
        orig_candidates = [m for m in found_matches if m["is_orig"] and not m["is_disc"]]
        disc_candidates = [m for m in found_matches if m["is_disc"] and not m["is_orig"]]

        if orig_candidates and disc_candidates:
            original_price = orig_candidates[0]["amount"]
            discounted_price = disc_candidates[0]["amount"]
        elif orig_candidates and not disc_candidates:
            original_price = orig_candidates[0]["amount"]
            remaining = [m for m in found_matches if m != orig_candidates[0]]
            discounted_price = remaining[0]["amount"] if remaining else None
        elif disc_candidates and not orig_candidates:
            discounted_price = disc_candidates[0]["amount"]
            remaining = [m for m in found_matches if m != disc_candidates[0]]
            original_price = remaining[0]["amount"] if remaining else None
        else:
            # No clear contextual cues: in e-commerce, lower price is deal price, higher is original MRP
            amounts = [m["amount"] for m in found_matches]
            discounted_price = min(amounts)
            original_price = max(amounts)

        # Enforce sanity: discounted price cannot exceed original price
        if original_price is not None and discounted_price is not None:
            if discounted_price > original_price:
                original_price, discounted_price = discounted_price, original_price

    elif len(found_matches) == 1:
        single = found_matches[0]
        if single["is_orig"] and not single["is_disc"]:
            original_price = single["amount"]
        else:
            # In e-commerce promo notifications, single price is the advertised deal price
            discounted_price = single["amount"]

    # Calculate missing prices or discount percent
    discount_percent = explicit_discount_pct

    if original_price is not None and discounted_price is not None:
        if original_price > discounted_price and discount_percent is None:
            calculated_pct = ((original_price - discounted_price) / original_price) * 100.0
            discount_percent = round(calculated_pct, 2)
    elif discount_percent is not None:
        if discounted_price is not None and original_price is None:
            if 0 < discount_percent < 100:
                original_price = round(discounted_price / (1.0 - (discount_percent / 100.0)), 2)
        elif original_price is not None and discounted_price is None:
            if 0 < discount_percent <= 100:
                discounted_price = round(original_price * (1.0 - (discount_percent / 100.0)), 2)

    return PriceInfo(
        original_price=original_price,
        discounted_price=discounted_price,
        currency=currency,
        discount_percent=discount_percent,
        price_texts_found=price_texts_found,
    )
