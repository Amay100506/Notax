"""
Deal Scorer for NotifyIQ Smart Shopping Extension.

Evaluates and scores deal quality (0-100) based on discount depth, item value thresholds,
urgency/time-sensitivity keywords, seasonal festival sales, and platform reputation.
Provides transparent explainability reasons and quality tier classifications.
"""

import re
from typing import Optional, List, Tuple
from pydantic import BaseModel, Field

from backend.ai.shopping.price_extractor import PriceInfo, extract_prices


class DealScore(BaseModel):
    """
    Evaluated deal quality and urgency score for shopping notifications.
    """
    score: int = Field(ge=0, le=100)
    quality_label: str  # "excellent", "good", "fair", "poor"
    reasons: list[str] = Field(default_factory=list)
    is_time_sensitive: bool = False


# Platform reputation registries
TIER_1_APPS = {
    "amazon": "Amazon",
    "com.amazon.mshop.android.shopping": "Amazon",
    "flipkart": "Flipkart",
    "com.flipkart.android": "Flipkart",
    "myntra": "Myntra",
    "com.myntra.android": "Myntra",
    "ajio": "Ajio",
    "com.ril.ajio": "Ajio",
    "tataneu": "Tata Neu",
    "tata neu": "Tata Neu",
    "tata cliq": "Tata CLiQ",
    "com.tatadigital.tcp": "Tata Neu",
    "nykaa": "Nykaa",
    "com.fsn.nykaa": "Nykaa",
    "croma": "Croma",
    "com.croma.app": "Croma",
    "reliance digital": "Reliance Digital",
    "com.reliancedigital": "Reliance Digital",
}

TIER_2_APPS = {
    "swiggy": "Swiggy",
    "in.swiggy.android": "Swiggy",
    "instamart": "Swiggy Instamart",
    "zomato": "Zomato",
    "com.application.zomato": "Zomato",
    "blinkit": "Blinkit",
    "zepto": "Zepto",
    "com.zeptonow.android": "Zepto",
    "bigbasket": "BigBasket",
    "bbnow": "BigBasket bbnow",
    "com.bigbasket.mobileapp": "BigBasket",
    "phonepe": "PhonePe",
    "com.phonepe.app": "PhonePe",
    "paytm": "Paytm",
    "net.one97.paytm": "Paytm",
}

# Seasonal / Festival Sale keywords
FESTIVAL_EVENTS = [
    (r'\b(?:big\s*billion(?:\s*days?)?|bbd)\b', "Flipkart Big Billion Days"),
    (r'\bgreat\s*indian(?:\s*festival)?\b', "Amazon Great Indian Festival"),
    (r'\bprime\s*day\b', "Amazon Prime Day"),
    (r'\bdiwali(?:\s*sale|\s*dhamaka|\s*offer|\s*special)?\b', "Diwali Mega Sale"),
    (r'\bblack\s*friday\b', "Black Friday Sale"),
    (r'\bcyber\s*monday\b', "Cyber Monday"),
    (r'\b(?:end\s*of\s*season(?:\s*sale)?|eoss)\b', "End of Season Sale (EOSS)"),
    (r'\bnew\s*year(?:\s*sale|\s*offer)?\b', "New Year Sale"),
    (r'\bchristmas(?:\s*sale|\s*deal)?\b', "Christmas Sale"),
    (r'\b(?:independence\s*day|freedom\s*sale)\b', "Independence Day Freedom Sale"),
    (r'\brepublic\s*day\b', "Republic Day Sale"),
    (r'\b(?:holi|dussehra|durga\s*puja)\b', "Festive Celebration Sale"),
]

# Urgency / Time sensitivity keywords
URGENCY_PATTERNS = [
    (r'\bflash\s*sale\b', "Flash sale active", 12),
    (r'\blightning\s*deal\b', "Lightning deal active", 12),
    (r'\blimited\s*time\b', "Limited time offer", 10),
    (r'\blast\s*chance\b', "Last chance deal", 10),
    (r'\bending\s*soon\b', "Offer ending soon", 10),
    (r'\bends\s*(?:today|tonight|midnight)\b', "Offer expires today", 10),
    (r'\btoday\s*only\b', "Valid today only", 10),
    (r'\b(?:hours?|mins?|minutes?)\s*left\b', "Expiring countdown running", 10),
    (r'\bdeal\s*of\s*the\s*day\b', "Deal of the day", 8),
    (r'\bhurry\b', "Urgent call to action", 5),
    (r'\bvalid\s*till\b', "Time-bound expiration", 5),
]

# Price drop / Historical low keywords
PRICE_DROP_PATTERNS = [
    (r'\blowest\s*price\b', "Historic lowest price indicator", 15),
    (r'\bprice\s*drop\b', "Direct price drop alert", 15),
    (r'\ball-?time\s*low\b', "All-time low price record", 15),
    (r'\bprice\s*slashed\b', "Price slashed promotion", 12),
    (r'\bsteep\s*drop\b', "Steep price drop", 12),
    (r'\bloot\s*deal\b', "Loot deal alert", 8),
    (r'\bsteal\s*deal\b', "Steal deal pricing", 8),
    (r'\bclearance(?:\s*sale)?\b', "Inventory clearance deal", 8),
]


def _detect_app_reputation(
    app_name: Optional[str] = None,
    package_name: Optional[str] = None,
    text: str = ""
) -> Tuple[int, Optional[str]]:
    """Identifies the e-commerce app tier and brand reputation."""
    candidates = []
    if package_name:
        candidates.append(package_name.lower().strip())
    if app_name:
        candidates.append(app_name.lower().strip())

    # Check Tier 1
    for key, name in TIER_1_APPS.items():
        if any(key in c for c in candidates) or re.search(rf'\b{re.escape(key)}\b', text, re.IGNORECASE):
            return 15, name

    # Check Tier 2
    for key, name in TIER_2_APPS.items():
        if any(key in c for c in candidates) or re.search(rf'\b{re.escape(key)}\b', text, re.IGNORECASE):
            return 10, name

    return 0, None


def score_deal(
    text: str,
    title: str = "",
    price_info: Optional[PriceInfo] = None,
    app_name: Optional[str] = None,
    package_name: Optional[str] = None,
) -> DealScore:
    """
    Evaluates deal quality score (0-100) and factors for shopping notifications.

    Scoring Factors:
    - Discount percentage (higher = better deal)
    - Price threshold (penalizes suspiciously cheap/junk items, rewards high-ticket savings)
    - Keywords: "flash sale", "limited time", "last chance", "ending soon", "lowest price", "price drop"
    - Seasonal/festival sales: "Diwali", "Big Billion", "Great Indian", "Prime Day", "Black Friday"
    - Source app reputation (Amazon, Flipkart, Myntra, etc.)

    Returns:
        DealScore Pydantic model with: score, quality_label, reasons, is_time_sensitive.
    """
    combined = f"{title}. {text}".strip() if title else text.strip()
    if not combined:
        return DealScore(
            score=0,
            quality_label="poor",
            reasons=["Empty notification text"],
            is_time_sensitive=False,
        )

    # Automatically extract price info if not provided
    if price_info is None:
        price_info = extract_prices(text, title)

    reasons: list[str] = []
    is_time_sensitive = False
    total_score = 0

    # 1. Festival / Seasonal Sale Detection
    festival_matched = False
    for pat, event_name in FESTIVAL_EVENTS:
        if re.search(pat, combined, re.IGNORECASE):
            total_score += 18
            reasons.append(f"Major shopping festival event: {event_name} (+18)")
            festival_matched = True
            break

    # 2. Urgency & Time-Sensitivity Keywords
    urgency_matched = False
    for pat, reason_desc, pts in URGENCY_PATTERNS:
        if re.search(pat, combined, re.IGNORECASE):
            is_time_sensitive = True
            if not urgency_matched:
                total_score += pts
                reasons.append(f"{reason_desc} (+{pts})")
                urgency_matched = True

    # 3. Price Drop & Historical Low Keywords
    price_drop_matched = False
    for pat, reason_desc, pts in PRICE_DROP_PATTERNS:
        if re.search(pat, combined, re.IGNORECASE):
            if not price_drop_matched:
                total_score += pts
                reasons.append(f"{reason_desc} (+{pts})")
                price_drop_matched = True

    # 4. Source App Reputation
    app_pts, recognized_app = _detect_app_reputation(app_name, package_name, combined)
    if app_pts > 0 and recognized_app:
        total_score += app_pts
        reasons.append(f"Verified trusted platform: {recognized_app} (+{app_pts})")

    # 5. Coupon / Promo Code Mention
    if re.search(r'(?i)\b(?:use|apply|enter)\s+(?:code|coupon|promo|voucher)\b|\bcoupon\s*code\b|\bcode:\s*[A-Z0-9]', combined):
        total_score += 7
        reasons.append("Applicable promo / coupon code available (+7)")

    # 6. Discount Percentage Evaluation
    discount_pts = 0
    if price_info.discount_percent is not None:
        pct = price_info.discount_percent
        if pct >= 70.0:
            discount_pts = 35
            reasons.append(f"Massive discount of {pct:.1f}% (+35)")
        elif pct >= 50.0:
            discount_pts = 28
            reasons.append(f"Substantial discount of {pct:.1f}% (+28)")
        elif pct >= 30.0:
            discount_pts = 20
            reasons.append(f"Solid discount of {pct:.1f}% (+20)")
        elif pct >= 15.0:
            discount_pts = 12
            reasons.append(f"Moderate discount of {pct:.1f}% (+12)")
        elif pct > 0:
            discount_pts = 5
            reasons.append(f"Small discount of {pct:.1f}% (+5)")

        total_score += discount_pts

    # Verified dual price savings bonus
    if price_info.original_price and price_info.discounted_price:
        if price_info.original_price > price_info.discounted_price:
            total_score += 5
            curr_sym = "₹" if price_info.currency == "INR" else ("$" if price_info.currency == "USD" else "")
            diff = round(price_info.original_price - price_info.discounted_price, 2)
            reasons.append(f"Verified price savings of {curr_sym}{diff} (+5)")

    # 7. Price Threshold Evaluation (Very cheap items get lower scores)
    curr = price_info.currency or "INR"
    disc_price = price_info.discounted_price

    if disc_price is not None:
        if curr == "INR":
            if disc_price < 50.0:
                total_score -= 18
                reasons.append(f"Extremely cheap item (₹{disc_price:.0f} < ₹50): high probability of spam/junk/sample (-18)")
            elif disc_price < 150.0:
                total_score -= 6
                reasons.append(f"Low-ticket item (₹{disc_price:.0f} < ₹150) (-6)")
            elif 500.0 <= disc_price <= 25000.0:
                total_score += 8
                reasons.append(f"Prime consumer goods price bracket (₹{disc_price:.0f}) (+8)")
            elif disc_price > 25000.0:
                total_score += 10
                reasons.append(f"High-value purchase item with large absolute monetary savings (+10)")
        elif curr == "USD":
            if disc_price < 2.0:
                total_score -= 18
                reasons.append(f"Extremely cheap item (${disc_price:.2f} < $2): high probability of clickbait/spam (-18)")
            elif disc_price < 5.0:
                total_score -= 6
                reasons.append(f"Low-ticket item (${disc_price:.2f} < $5) (-6)")
            elif 15.0 <= disc_price <= 500.0:
                total_score += 8
                reasons.append(f"Prime consumer goods price bracket (${disc_price:.2f}) (+8)")
            elif disc_price > 500.0:
                total_score += 10
                reasons.append(f"High-value purchase item with large absolute monetary savings (+10)")

    # 8. Check if ANY shopping signals were detected
    has_shopping_signals = bool(
        festival_matched
        or urgency_matched
        or price_drop_matched
        or app_pts > 0
        or price_info.discount_percent
        or price_info.price_texts_found
        or re.search(r'(?i)\b(?:sale|discount|deal|offer|shop|buy|cart|order|cashback)\b', combined)
    )

    if not has_shopping_signals:
        return DealScore(
            score=0,
            quality_label="poor",
            reasons=["No shopping deal signals detected in notification"],
            is_time_sensitive=False,
        )

    # Base points for verified shopping notification
    total_score += 10
    reasons.insert(0, "Shopping notification identified (+10)")

    # Final clamping between 0 and 100
    final_score = max(0, min(100, total_score))

    # Quality Label determination
    if final_score >= 80:
        quality_label = "excellent"
    elif final_score >= 60:
        quality_label = "good"
    elif final_score >= 40:
        quality_label = "fair"
    else:
        quality_label = "poor"

    return DealScore(
        score=final_score,
        quality_label=quality_label,
        reasons=reasons,
        is_time_sensitive=is_time_sensitive,
    )
