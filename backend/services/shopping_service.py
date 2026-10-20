"""
Shopping Intelligence Service for NotifyIQ.
Orchestrates price extraction, deal scoring, coupon detection,
historical price tracking, price drop alerts, and shopping analytics.
"""

from collections import defaultdict
from datetime import datetime, timezone
import json
from pathlib import Path
import re
from typing import Any, Optional
import uuid

from pydantic import BaseModel, Field

from backend.database.connection import get_db_connection, get_db_path
from backend.database.repository import Repository
from backend.utils.logging_config import logger


# ============================================================================
# Pydantic Schemas / Models
# ============================================================================

class PriceDropAlert(BaseModel):
    """Alert triggered when a significant price reduction is detected."""
    product_title: str
    current_price: float
    previous_price: float
    drop_amount: float
    drop_percent: float
    lowest_price: float
    highest_price: float
    average_price: float
    currency: str = "INR"
    is_all_time_low: bool = False
    detected_at: str
    message: str


class TopStore(BaseModel):
    """Store ranking item by shopping notification volume."""
    package_name: str
    store_name: str
    count: int


class ShoppingSummary(BaseModel):
    """Aggregated shopping intelligence summary."""
    total_shopping_notifications: int
    active_deals_count: int
    coupons_found: int
    avg_discount_percent: float
    top_stores: list[TopStore]
    price_drops_detected: int


class ShoppingAnalysis(BaseModel):
    """Complete multi-faceted shopping analysis for a single notification."""
    notification_id: Optional[str] = None
    product_title: Optional[str] = None
    original_price: Optional[float] = None
    discounted_price: Optional[float] = None
    discount_percent: Optional[float] = None
    currency: str = "INR"
    deal_score: float = 0.0
    quality_label: str = "regular"
    coupon_codes: list[str] = Field(default_factory=list)
    is_time_sensitive: bool = False
    is_shopping: bool = False
    price_drop: Optional[PriceDropAlert] = None
    extracted_prices: list[float] = Field(default_factory=list)
    deal_reasons: list[str] = Field(default_factory=list)


# ============================================================================
# Extractor & Scorer Implementations
# ============================================================================

class PriceExtractor:
    """
    Extracts price points, discounts, and currency symbols from notification text.
    Handles INR (₹, Rs), USD ($), EUR (€), and GBP (£).
    """

    CURRENCY_SYMBOLS: dict[str, str] = {
        "₹": "INR",
        "rs": "INR",
        "rs.": "INR",
        "inr": "INR",
        "$": "USD",
        "usd": "USD",
        "€": "EUR",
        "eur": "EUR",
        "£": "GBP",
        "gbp": "GBP",
    }

    # Common shopping app prefix patterns to clean from titles
    STORE_PREFIX_PATTERNS = [
        r"^(?:amazon|flipkart|myntra|swiggy|zomato|blinkit|zepto|ajio|tata\s*cliq|nykaa|meesho)[:\s\-|]+",
        r"^(?:special\s*offer|deal\s*alert|flash\s*sale|price\s*drop)[:\s\-|]+",
    ]

    def extract_prices(self, text: str, title: str = "") -> dict[str, Any]:
        """
        Parses text and title for numeric prices, original prices, discounts, and currency.
        """
        combined = f"{title}. {text}".strip()
        if not combined or combined == ".":
            return {
                "has_price": False,
                "original_price": None,
                "discounted_price": None,
                "current_price": None,
                "discount_percent": None,
                "currency": "INR",
                "extracted_prices": [],
                "product_title": None,
            }

        # 1. Detect Currency
        currency = "INR"
        curr_match = re.search(r"(?:₹|\b(?:rs\.?|inr)\b|\$|\b(?:usd|eur|gbp)\b|€|£)", combined, re.IGNORECASE)
        if curr_match:
            symbol_key = curr_match.group(0).lower().strip()
            currency = self.CURRENCY_SYMBOLS.get(symbol_key, "INR")

        # 2. Extract explicit discount percent (e.g., '40% off', 'flat 50% discount')
        discount_percent: Optional[float] = None
        pct_match = re.search(
            r"(?:flat\s+|up\s*to\s+|save\s+)?(\d{1,2}(?:\.\d{1,2})?)\s*%\s*(?:off|discount|cashback)?",
            combined,
            re.IGNORECASE,
        )
        if pct_match:
            val = float(pct_match.group(1))
            if 0 < val <= 99:
                discount_percent = val

        # 3. Extract Original / MRP / Was price
        original_price: Optional[float] = None
        orig_match = re.search(
            r"(?:was|mrp|originally|before|worth|strike)\s*[:\s]*"
            r"(?:₹|\$|€|£|rs\.?|inr)?\s*([0-9]{1,3}(?:,[0-9]{2,3})*(?:\.[0-9]{1,2})?|[0-9]+(?:\.[0-9]{1,2})?)",
            combined,
            re.IGNORECASE,
        )
        if orig_match:
            try:
                num_str = orig_match.group(1).replace(",", "")
                original_price = float(num_str)
            except ValueError:
                original_price = None

        # 4. Extract Discounted / Sale / Now price
        discounted_price: Optional[float] = None
        now_match = re.search(
            r"(?:now\s*(?:at|for|only)?|just|for|at|sale\s*price|deal\s*price|offer\s*price)\s*[:\s]*"
            r"(?:₹|\$|€|£|rs\.?|inr)?\s*([0-9]{1,3}(?:,[0-9]{2,3})*(?:\.[0-9]{1,2})?|[0-9]+(?:\.[0-9]{1,2})?)",
            combined,
            re.IGNORECASE,
        )
        if now_match:
            try:
                num_str = now_match.group(1).replace(",", "")
                discounted_price = float(num_str)
            except ValueError:
                discounted_price = None

        # 5. Extract all candidate prices
        price_candidates = re.findall(
            r"(?:₹|\$|€|£|\brs\.?|\binr)\s*([0-9]{1,3}(?:,[0-9]{2,3})*(?:\.[0-9]{1,2})?|[0-9]+(?:\.[0-9]{1,2})?)",
            combined,
            re.IGNORECASE,
        )
        extracted_floats: list[float] = []
        for p in price_candidates:
            try:
                val = float(p.replace(",", ""))
                if 1.0 <= val <= 10_000_000:
                    if val not in extracted_floats:
                        extracted_floats.append(val)
            except ValueError:
                continue

        # If discounted_price was not found by pattern, choose the lowest candidate
        if discounted_price is None and extracted_floats:
            if len(extracted_floats) >= 2 and original_price is None:
                # Typically the lower price is current/deal price and higher is original
                discounted_price = min(extracted_floats[0], extracted_floats[1])
                original_price = max(extracted_floats[0], extracted_floats[1])
            else:
                discounted_price = extracted_floats[0]

        # If original_price was found and discounted_price was found, calculate discount_percent if missing
        if original_price and discounted_price and original_price > discounted_price:
            calc_pct = round(((original_price - discounted_price) / original_price) * 100, 1)
            if discount_percent is None:
                discount_percent = calc_pct

        # If only discounted_price and discount_percent exist, estimate original price
        if discounted_price and discount_percent and not original_price and discount_percent < 100:
            original_price = round(discounted_price / (1.0 - (discount_percent / 100.0)), 2)

        # 6. Extract clean product title
        product_title: Optional[str] = None
        if title:
            clean_title = title.strip()
            for pat in self.STORE_PREFIX_PATTERNS:
                clean_title = re.sub(pat, "", clean_title, flags=re.IGNORECASE).strip()
            # Clean trailing punctuation
            clean_title = re.sub(r"[\-–:|]+$", "", clean_title).strip()
            if clean_title:
                product_title = clean_title

        if not product_title and text:
            # First 6 words of text before price or punctuation
            parts = re.split(r"[.!?\n]|(?:at|now|just|for|save|mrp)\s*(?:₹|\$|€|£|rs)", text, flags=re.IGNORECASE)
            if parts and parts[0].strip():
                candidate = parts[0].strip()
                words = candidate.split()
                if len(words) > 7:
                    candidate = " ".join(words[:7])
                product_title = candidate

        has_price = bool(discounted_price is not None or original_price is not None or extracted_floats)

        return {
            "has_price": has_price,
            "original_price": original_price,
            "discounted_price": discounted_price,
            "current_price": discounted_price or (extracted_floats[0] if extracted_floats else None),
            "discount_percent": discount_percent,
            "currency": currency,
            "extracted_prices": extracted_floats,
            "product_title": product_title,
        }


class DealScorer:
    """
    Evaluates deals based on depth of discount, absolute savings,
    time urgency, and retailer authority.
    Outputs a deal score between 0.0 and 100.0.
    """

    TRUSTED_SHOPPING_PACKAGES: set[str] = {
        "in.amazon.mShop.android.shopping",
        "com.amazon.mShop.android.shopping",
        "com.flipkart.android",
        "com.myntra.android",
        "com.ril.ajio",
        "in.swiggy.android",
        "com.application.zomato",
        "com.tul.tatacliq",
        "com.grofers.customerapp",
        "com.zeptoconsumerapp",
        "com.fsn.nykaa",
        "com.meesho.supply",
    }

    TIME_SENSITIVE_KEYWORDS = [
        "flash sale",
        "deal of the day",
        "lightning deal",
        "ends tonight",
        "limited time",
        "hurry",
        "last chance",
        "expires in",
        "today only",
        "only today",
        "midnight",
        "hours left",
        "few left",
        "stock ending",
    ]

    def score_deal(
        self,
        text: str,
        title: str,
        package_name: str,
        price_info: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Calculates deal score and assigns quality label.
        """
        combined = f"{title}. {text}".lower()
        score = 0.0
        reasons: list[str] = []

        # 1. Discount Percentage Impact (Up to 45 pts)
        discount_pct = price_info.get("discount_percent")
        if discount_pct is not None:
            if discount_pct >= 70.0:
                score += 45.0
                reasons.append(f"Massive discount of {discount_pct:.0f}%")
            elif discount_pct >= 50.0:
                score += 35.0
                reasons.append(f"Deep discount of {discount_pct:.0f}%")
            elif discount_pct >= 30.0:
                score += 25.0
                reasons.append(f"Significant discount of {discount_pct:.0f}%")
            elif discount_pct >= 15.0:
                score += 15.0
                reasons.append(f"Moderate discount of {discount_pct:.0f}%")
            elif discount_pct > 0.0:
                score += 5.0
                reasons.append(f"Discount of {discount_pct:.0f}%")

        # 2. Absolute Savings Impact (Up to 20 pts)
        orig = price_info.get("original_price")
        disc = price_info.get("discounted_price")
        if orig and disc and orig > disc:
            savings = orig - disc
            currency = price_info.get("currency", "INR")
            curr_sym = "₹" if currency == "INR" else ("$" if currency == "USD" else currency)
            if savings >= 5000:
                score += 20.0
                reasons.append(f"High absolute savings of {curr_sym}{savings:,.0f}")
            elif savings >= 1500:
                score += 15.0
                reasons.append(f"Substantial savings of {curr_sym}{savings:,.0f}")
            elif savings >= 400:
                score += 10.0
                reasons.append(f"Solid savings of {curr_sym}{savings:,.0f}")
            elif savings > 0:
                score += 5.0

        # 3. Time Urgency (Up to 15 pts)
        is_time_sensitive = any(kw in combined for kw in self.TIME_SENSITIVE_KEYWORDS)
        if is_time_sensitive:
            score += 15.0
            reasons.append("Time-sensitive deal urgency")

        # 4. Trusted Retailer / Source App (Up to 15 pts)
        pkg_lower = package_name.lower()
        if (
            pkg_lower in self.TRUSTED_SHOPPING_PACKAGES
            or any(store in pkg_lower for store in ["amazon", "flipkart", "myntra", "swiggy", "zomato", "blinkit", "zepto"])
        ):
            score += 15.0
            reasons.append("Verified shopping retailer")

        # 5. Generic Price Mention Presence (5 pts baseline)
        if price_info.get("has_price") and score == 0.0:
            score += 20.0
            reasons.append("Price observed")

        # 6. Quality Label Mapping
        score = min(100.0, max(0.0, round(score, 1)))
        if score >= 75.0:
            quality_label = "exceptional_deal"
        elif score >= 55.0:
            quality_label = "great_deal"
        elif score >= 35.0:
            quality_label = "good_deal"
        elif score >= 20.0:
            quality_label = "fair_deal"
        else:
            quality_label = "regular"

        return {
            "deal_score": score,
            "quality_label": quality_label,
            "is_time_sensitive": is_time_sensitive,
            "reasons": reasons,
            "expires_at": None,
        }


class CouponDetector:
    """
    Detects coupon, promo, and voucher codes using regex patterns
    while filtering out common false positives.
    """

    FALSE_POSITIVES = {
        "HTTP", "HTTPS", "HTML", "JSON", "TODAY", "ORDER", "UPDATE", "ALERT",
        "NOTIFICATION", "ANDROID", "GOOGLE", "AMAZON", "FLIPKART", "OFFER",
        "DEAL", "DISCOUNT", "PRICE", "PERCENT", "FREE", "SALE", "SHOP", "ITEMS",
        "LIMITED", "URGENT", "VALID", "CLICK", "HERE", "NOW", "VIEW", "TERMS",
        "CONDITIONS", "APPLY", "MORE", "INFO", "APP", "INDIA", "FLAT", "SAVE",
    }

    def detect_coupons(self, text: str, title: str = "") -> list[str]:
        """
        Scans text and title for voucher/promo codes.
        Returns a list of clean, uppercase code strings.
        """
        combined = f"{title} {text}".strip()
        if not combined:
            return []

        found_codes: set[str] = set()

        # Pattern 1: Direct directive like "use code FLAT50", "coupon: SAVE20", "apply code SWIGGYIT"
        p1 = re.findall(
            r"(?:use|apply|code|coupon|promo|voucher)\s*(?:code)?\s*[:\s\-]\s*([A-Za-z0-9_\-#]{3,16})\b",
            combined,
            re.IGNORECASE,
        )
        for code in p1:
            clean = code.strip().upper().rstrip(".,;:!?")
            if len(clean) >= 3 and clean not in self.FALSE_POSITIVES and not clean.isdigit():
                found_codes.add(clean)

        # Pattern 2: Explicit prefix CODE: XYZ
        p2 = re.findall(r"\b(?:CODE|COUPON|PROMO|VOUCHER)[:\s]+([A-Za-z0-9_\-#]{3,16})\b", combined)
        for code in p2:
            clean = code.strip().upper().rstrip(".,;:!?")
            if len(clean) >= 3 and clean not in self.FALSE_POSITIVES and not clean.isdigit():
                found_codes.add(clean)

        # Pattern 3: Common standalone promotional tokens like FLAT50, SAVE200, DIWALI100
        p3 = re.findall(
            r"\b((?:FLAT|SAVE|GET|OFF|EXTRA|CASH|FESTIVE|DIWALI|HOLI|SUMMER|WINTER|WELCOME|NEW|FIRST)[0-9]{1,4})\b",
            combined,
            re.IGNORECASE,
        )
        for code in p3:
            clean = code.strip().upper()
            if clean not in self.FALSE_POSITIVES:
                found_codes.add(clean)

        return sorted(list(found_codes))


# Exported module-level extractor singletons
price_extractor = PriceExtractor()
deal_scorer = DealScorer()
coupon_detector = CouponDetector()


# ============================================================================
# Shopping Service Orchestrator
# ============================================================================

class ShoppingService:
    """
    Core orchestrator for all shopping intelligence operations:
    notification analysis, price tracking, history retrieval,
    deal curation, coupon harvesting, and summary analytics.
    """

    def __init__(
        self,
        repository: Optional[Repository] = None,
        db_path: Optional[str] = None,
        price_extractor_instance: Optional[PriceExtractor] = None,
        deal_scorer_instance: Optional[DealScorer] = None,
        coupon_detector_instance: Optional[CouponDetector] = None,
    ):
        self.repository = repository or Repository(db_path=db_path)
        self.db_path = db_path or (self.repository.db_path if self.repository else None)
        self.price_extractor = price_extractor_instance or price_extractor
        self.deal_scorer = deal_scorer_instance or deal_scorer
        self.coupon_detector = coupon_detector_instance or coupon_detector

        # Ensure shopping schema tables exist
        self.ensure_shopping_tables()

    def ensure_shopping_tables(self) -> None:
        """
        Creates SQLite tables `price_history` and `shopping_deals` if they do not exist.
        Also configures relevant performance indexes and ensures base notifications schema exists.
        """
        from backend.database.connection import init_db
        init_db(self.db_path)

        with get_db_connection(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS price_history (
                    id TEXT PRIMARY KEY,
                    product_title TEXT NOT NULL,
                    package_name TEXT,
                    price REAL NOT NULL,
                    currency TEXT DEFAULT 'INR',
                    notification_id TEXT,
                    observed_at TEXT NOT NULL
                );
                """
            )
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS shopping_deals (
                    id TEXT PRIMARY KEY,
                    notification_id TEXT NOT NULL,
                    product_title TEXT,
                    original_price REAL,
                    discounted_price REAL,
                    discount_percent REAL,
                    deal_score REAL,
                    quality_label TEXT,
                    coupon_codes TEXT,
                    is_time_sensitive INTEGER DEFAULT 0,
                    source_app TEXT,
                    detected_at TEXT NOT NULL,
                    expires_at TEXT,
                    FOREIGN KEY (notification_id) REFERENCES notifications(id) ON DELETE CASCADE
                );
                """
            )
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_price_history_product_title ON price_history(product_title);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_price_history_observed_at ON price_history(observed_at);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_shopping_deals_notification_id ON shopping_deals(notification_id);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_shopping_deals_deal_score ON shopping_deals(deal_score);")
            conn.commit()
            logger.debug("Shopping database tables ensured (price_history, shopping_deals).")

    def track_price(
        self,
        package_name: str,
        product_title: str,
        price: float,
        currency: str = "INR",
        notification_id: Optional[str] = None,
    ) -> dict[str, Any]:
        """
        Records an individual price observation in SQLite `price_history`.
        """
        record_id = str(uuid.uuid4())
        observed_at = datetime.now(timezone.utc).isoformat()

        with get_db_connection(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO price_history (
                    id, product_title, package_name, price, currency, notification_id, observed_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record_id,
                    product_title,
                    package_name,
                    float(price),
                    currency,
                    notification_id,
                    observed_at,
                ),
            )
            conn.commit()

        return {
            "id": record_id,
            "product_title": product_title,
            "package_name": package_name,
            "price": float(price),
            "currency": currency,
            "notification_id": notification_id,
            "observed_at": observed_at,
        }

    def get_price_history(self, product_title: str, limit: int = 50) -> list[dict[str, Any]]:
        """
        Returns chronological price history for a given product title.
        Supports exact and substring matching.
        """
        with get_db_connection(self.db_path) as conn:
            cursor = conn.cursor()
            # First attempt exact case-insensitive match
            cursor.execute(
                """
                SELECT * FROM price_history
                WHERE LOWER(product_title) = LOWER(?)
                ORDER BY observed_at DESC
                LIMIT ?
                """,
                (product_title, limit),
            )
            rows = cursor.fetchall()

            # If no exact match, fallback to substring match
            if not rows:
                cursor.execute(
                    """
                    SELECT * FROM price_history
                    WHERE LOWER(product_title) LIKE LOWER(?)
                    ORDER BY observed_at DESC
                    LIMIT ?
                    """,
                    (f"%{product_title}%", limit),
                )
                rows = cursor.fetchall()

            return [dict(row) for row in rows]

    def detect_price_drop(self, product_title: str, current_price: float) -> Optional[PriceDropAlert]:
        """
        Compares current price with historical observations for the product.
        Returns a PriceDropAlert if a significant drop (>= 3% or >= Rs 10) is detected.
        """
        with get_db_connection(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT price, currency, observed_at FROM price_history
                WHERE LOWER(product_title) = LOWER(?)
                ORDER BY observed_at DESC
                """,
                (product_title,),
            )
            rows = cursor.fetchall()

            if not rows:
                cursor.execute(
                    """
                    SELECT price, currency, observed_at FROM price_history
                    WHERE LOWER(product_title) LIKE LOWER(?)
                    ORDER BY observed_at DESC
                    """,
                    (f"%{product_title}%",),
                )
                rows = cursor.fetchall()

        if not rows:
            return None

        prices = [float(r["price"]) for r in rows]
        currencies = [r["currency"] for r in rows if r["currency"]]
        currency = currencies[0] if currencies else "INR"

        previous_price = prices[0]
        lowest_price = min(prices)
        highest_price = max(prices)
        average_price = sum(prices) / len(prices)

        # Check for drop relative to the latest recorded observation
        if current_price < previous_price:
            drop_amount = previous_price - current_price
            drop_percent = (drop_amount / previous_price) * 100.0

            # Meaningful drop threshold
            if drop_percent >= 3.0 or drop_amount >= 10.0:
                is_all_time_low = current_price < lowest_price
                curr_sym = "₹" if currency == "INR" else ("$" if currency == "USD" else currency)
                msg = (
                    f"Price drop of {drop_percent:.1f}% ({curr_sym}{drop_amount:,.2f}) detected for '{product_title}'. "
                    f"Now {curr_sym}{current_price:,.2f} (was {curr_sym}{previous_price:,.2f})."
                )
                if is_all_time_low:
                    msg += " All-time lowest recorded price!"

                return PriceDropAlert(
                    product_title=product_title,
                    current_price=float(current_price),
                    previous_price=float(previous_price),
                    drop_amount=round(drop_amount, 2),
                    drop_percent=round(drop_percent, 2),
                    lowest_price=float(min(lowest_price, current_price)),
                    highest_price=float(highest_price),
                    average_price=round(average_price, 2),
                    currency=currency,
                    is_all_time_low=is_all_time_low,
                    detected_at=datetime.now(timezone.utc).isoformat(),
                    message=msg,
                )

        return None

    def save_deal(self, deal_data: dict[str, Any]) -> dict[str, Any]:
        """
        Inserts or replaces a curated deal into SQLite `shopping_deals`.
        Ensures foreign key compatibility with notifications table.
        """
        record_id = deal_data.get("id") or str(uuid.uuid4())
        notification_id = deal_data.get("notification_id") or str(uuid.uuid4())
        detected_at = deal_data.get("detected_at") or datetime.now(timezone.utc).isoformat()

        coupon_codes_val = deal_data.get("coupon_codes", [])
        if isinstance(coupon_codes_val, list):
            coupon_codes_str = json.dumps(coupon_codes_val)
        else:
            coupon_codes_str = str(coupon_codes_val) if coupon_codes_val else "[]"

        with get_db_connection(self.db_path) as conn:
            cursor = conn.cursor()

            # Ensure notification_id exists in notifications to satisfy FOREIGN KEY constraint
            cursor.execute("SELECT 1 FROM notifications WHERE id = ?", (notification_id,))
            if not cursor.fetchone():
                cursor.execute(
                    """
                    INSERT OR IGNORE INTO notifications (
                        id, event_id, package_name, title, text, category, category_confidence,
                        model_type, priority_score, priority_level, urgency_score, action_score,
                        deadline_score, importance_score, recency_score, deadline_status,
                        priority_reasons, received_at, processed_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        notification_id,
                        f"event_{notification_id}",
                        deal_data.get("source_app") or "shopping.service",
                        deal_data.get("product_title") or "Shopping Deal",
                        deal_data.get("product_title") or "",
                        "promotional",
                        0.90,
                        "shopping_intelligence",
                        float(deal_data.get("deal_score") or 50.0),
                        "medium",
                        50.0,
                        0.0,
                        0.0,
                        50.0,
                        100.0,
                        "none",
                        "[]",
                        detected_at,
                        detected_at,
                    ),
                )

            cursor.execute(
                """
                INSERT OR REPLACE INTO shopping_deals (
                    id, notification_id, product_title, original_price, discounted_price,
                    discount_percent, deal_score, quality_label, coupon_codes,
                    is_time_sensitive, source_app, detected_at, expires_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record_id,
                    notification_id,
                    deal_data.get("product_title"),
                    deal_data.get("original_price"),
                    deal_data.get("discounted_price"),
                    deal_data.get("discount_percent"),
                    float(deal_data.get("deal_score", 0.0)),
                    deal_data.get("quality_label", "regular"),
                    coupon_codes_str,
                    1 if deal_data.get("is_time_sensitive") else 0,
                    deal_data.get("source_app"),
                    detected_at,
                    deal_data.get("expires_at"),
                ),
            )
            conn.commit()

        return {
            "id": record_id,
            "notification_id": notification_id,
            "product_title": deal_data.get("product_title"),
            "deal_score": deal_data.get("deal_score"),
            "detected_at": detected_at,
        }

    def get_best_deals(self, limit: int = 50, min_score: float = 0.0) -> list[dict[str, Any]]:
        """
        Returns active deals sorted by deal score descending.
        """
        with get_db_connection(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT d.*, n.title as notification_title, n.text as notification_text, n.received_at
                FROM shopping_deals d
                LEFT JOIN notifications n ON d.notification_id = n.id
                WHERE d.deal_score >= ?
                ORDER BY d.deal_score DESC, d.detected_at DESC
                LIMIT ?
                """,
                (min_score, limit),
            )
            rows = cursor.fetchall()

            results: list[dict[str, Any]] = []
            for row in rows:
                item = dict(row)
                raw_coupons = item.get("coupon_codes")
                try:
                    item["coupon_codes"] = json.loads(raw_coupons or "[]")
                except Exception:
                    item["coupon_codes"] = [raw_coupons] if raw_coupons else []
                item["is_time_sensitive"] = bool(item.get("is_time_sensitive"))
                results.append(item)

            return results

    def get_shopping_summary(self) -> ShoppingSummary:
        """
        Computes aggregate shopping intelligence metrics:
        total shopping notifications, active deals, unique coupons,
        average discount percentage, top stores by volume, and price drops.
        """
        with get_db_connection(self.db_path) as conn:
            cursor = conn.cursor()

            # 1. Total Shopping Notifications
            cursor.execute(
                """
                SELECT COUNT(DISTINCT id) FROM notifications
                WHERE category = 'promotional'
                   OR id IN (SELECT notification_id FROM shopping_deals)
                """
            )
            total_notifs = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM shopping_deals")
            total_deals_rows = cursor.fetchone()[0]
            if total_notifs == 0 and total_deals_rows > 0:
                total_notifs = total_deals_rows

            # 2. Active Deals Count
            now_iso = datetime.now(timezone.utc).isoformat()
            cursor.execute(
                """
                SELECT COUNT(*) FROM shopping_deals
                WHERE expires_at IS NULL OR expires_at > ?
                """,
                (now_iso,),
            )
            active_deals = cursor.fetchone()[0]

            # 3. Unique Coupons Found
            cursor.execute(
                """
                SELECT coupon_codes FROM shopping_deals
                WHERE coupon_codes IS NOT NULL AND coupon_codes != '' AND coupon_codes != '[]'
                """
            )
            coupon_rows = cursor.fetchall()
            distinct_coupons: set[str] = set()
            for r in coupon_rows:
                raw_c = r["coupon_codes"]
                try:
                    parsed = json.loads(raw_c)
                    if isinstance(parsed, list):
                        for c in parsed:
                            if c:
                                distinct_coupons.add(str(c).strip().upper())
                    elif parsed:
                        distinct_coupons.add(str(parsed).strip().upper())
                except Exception:
                    if raw_c:
                        distinct_coupons.add(str(raw_c).strip().upper())

            coupons_found = len(distinct_coupons)

            # 4. Average Discount Percent
            cursor.execute(
                """
                SELECT AVG(discount_percent) FROM shopping_deals
                WHERE discount_percent IS NOT NULL AND discount_percent > 0
                """
            )
            avg_row = cursor.fetchone()
            avg_discount = float(avg_row[0]) if (avg_row and avg_row[0] is not None) else 0.0

            # 5. Top Stores
            cursor.execute(
                """
                SELECT source_app, COUNT(*) as count FROM shopping_deals
                WHERE source_app IS NOT NULL AND source_app != ''
                GROUP BY source_app
                ORDER BY count DESC
                LIMIT 5
                """
            )
            store_rows = cursor.fetchall()
            if not store_rows:
                cursor.execute(
                    """
                    SELECT package_name as source_app, COUNT(*) as count FROM notifications
                    WHERE category = 'promotional'
                    GROUP BY package_name
                    ORDER BY count DESC
                    LIMIT 5
                    """
                )
                store_rows = cursor.fetchall()

            friendly_names = {
                "in.amazon.mShop.android.shopping": "Amazon",
                "com.amazon.mShop.android.shopping": "Amazon",
                "com.amazon": "Amazon",
                "com.flipkart.android": "Flipkart",
                "com.myntra.android": "Myntra",
                "com.ril.ajio": "Ajio",
                "in.swiggy.android": "Swiggy",
                "com.application.zomato": "Zomato",
                "com.tul.tatacliq": "Tata CLiQ",
                "com.grofers.customerapp": "Blinkit",
                "com.zeptoconsumerapp": "Zepto",
                "com.fsn.nykaa": "Nykaa",
                "com.meesho.supply": "Meesho",
            }

            top_stores_list: list[TopStore] = []
            for row in store_rows:
                pkg = row["source_app"]
                disp_name = friendly_names.get(pkg)
                if not disp_name:
                    disp_name = pkg.split(".")[-1].capitalize() if "." in pkg else pkg.capitalize()
                top_stores_list.append(TopStore(
                    package_name=pkg,
                    store_name=disp_name,
                    count=row["count"],
                ))

            # 6. Price Drops Detected
            cursor.execute(
                """
                SELECT product_title, price, observed_at
                FROM price_history
                ORDER BY product_title, observed_at ASC
                """
            )
            history_rows = cursor.fetchall()
            drops_count = 0
            product_prices = defaultdict(list)
            for hr in history_rows:
                product_prices[hr["product_title"]].append(float(hr["price"]))

            for p_list in product_prices.values():
                for i in range(1, len(p_list)):
                    if p_list[i] < p_list[i - 1]:
                        drops_count += 1
                        break

            return ShoppingSummary(
                total_shopping_notifications=total_notifs,
                active_deals_count=active_deals,
                coupons_found=coupons_found,
                avg_discount_percent=round(avg_discount, 1),
                top_stores=top_stores_list,
                price_drops_detected=drops_count,
            )

    def get_all_coupons(self) -> list[dict[str, Any]]:
        """
        Lists all detected coupon codes with associated product context.
        """
        with get_db_connection(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT coupon_codes, product_title, discount_percent, source_app, deal_score, detected_at, expires_at
                FROM shopping_deals
                WHERE coupon_codes IS NOT NULL AND coupon_codes != '' AND coupon_codes != '[]'
                ORDER BY detected_at DESC
                """
            )
            rows = cursor.fetchall()

            unique_coupons: dict[str, dict[str, Any]] = {}
            for row in rows:
                raw = row["coupon_codes"]
                try:
                    codes = json.loads(raw)
                    if not isinstance(codes, list):
                        codes = [codes]
                except Exception:
                    codes = [raw]

                for c in codes:
                    code_clean = str(c).strip().upper()
                    if code_clean and code_clean not in unique_coupons:
                        unique_coupons[code_clean] = {
                            "coupon_code": code_clean,
                            "product_title": row["product_title"],
                            "discount_percent": row["discount_percent"],
                            "source_app": row["source_app"],
                            "deal_score": row["deal_score"],
                            "detected_at": row["detected_at"],
                            "expires_at": row["expires_at"],
                        }

            return list(unique_coupons.values())

    def analyze_shopping_notification(
        self,
        notification: dict[str, Any],
        persist: bool = False,
    ) -> ShoppingAnalysis:
        """
        Takes a processed notification and runs it through:
          - price_extractor.extract_prices(text, title)
          - deal_scorer.score_deal(text, title, package_name, price_info)
          - coupon_detector.detect_coupons(text, title)
        Returns a combined ShoppingAnalysis object.
        """
        title = notification.get("title") or ""
        text = notification.get("text") or notification.get("normalized_text") or ""
        package_name = notification.get("package_name") or ""
        notif_id = notification.get("id") or str(uuid.uuid4())

        # 1. Price Extraction
        price_info = self.price_extractor.extract_prices(text, title)

        # 2. Deal Scoring
        deal_info = self.deal_scorer.score_deal(text, title, package_name, price_info)

        # 3. Coupon Detection
        coupons = self.coupon_detector.detect_coupons(text, title)

        # Determine product title
        product_title = (
            price_info.get("product_title")
            or title
            or f"Product from {package_name}"
        )

        # Current observed price
        current_price = price_info.get("discounted_price") or price_info.get("current_price")

        # 4. Check for price drop alert
        price_drop_alert: Optional[PriceDropAlert] = None
        if current_price and product_title:
            price_drop_alert = self.detect_price_drop(product_title, current_price)

        # Determine if notification is shopping-related
        is_shopping = bool(
            price_info.get("has_price")
            or len(coupons) > 0
            or deal_info.get("deal_score", 0.0) >= 20.0
            or notification.get("category") == "promotional"
            or any(k in package_name.lower() for k in ["amazon", "flipkart", "myntra", "swiggy", "zomato", "blinkit", "zepto", "shop"])
        )

        # 5. Persist if requested
        if persist:
            if current_price and product_title:
                self.track_price(
                    package_name=package_name,
                    product_title=product_title,
                    price=current_price,
                    currency=price_info.get("currency", "INR"),
                    notification_id=notif_id,
                )

            if is_shopping and (deal_info.get("deal_score", 0.0) > 0.0 or price_info.get("has_price") or coupons):
                self.save_deal({
                    "id": str(uuid.uuid4()),
                    "notification_id": notif_id,
                    "product_title": product_title,
                    "original_price": price_info.get("original_price"),
                    "discounted_price": price_info.get("discounted_price"),
                    "discount_percent": price_info.get("discount_percent"),
                    "deal_score": deal_info.get("deal_score", 0.0),
                    "quality_label": deal_info.get("quality_label", "regular"),
                    "coupon_codes": coupons,
                    "is_time_sensitive": deal_info.get("is_time_sensitive", False),
                    "source_app": package_name,
                    "detected_at": datetime.now(timezone.utc).isoformat(),
                    "expires_at": deal_info.get("expires_at"),
                })

        return ShoppingAnalysis(
            notification_id=notif_id,
            product_title=product_title,
            original_price=price_info.get("original_price"),
            discounted_price=price_info.get("discounted_price"),
            discount_percent=price_info.get("discount_percent"),
            currency=price_info.get("currency", "INR"),
            deal_score=deal_info.get("deal_score", 0.0),
            quality_label=deal_info.get("quality_label", "regular"),
            coupon_codes=coupons,
            is_time_sensitive=deal_info.get("is_time_sensitive", False),
            is_shopping=is_shopping,
            price_drop=price_drop_alert,
            extracted_prices=price_info.get("extracted_prices", []),
            deal_reasons=deal_info.get("reasons", []),
        )

    def analyze_and_store(self, notification: dict[str, Any]) -> ShoppingAnalysis:
        """
        Convenience wrapper that analyzes a notification and persists
        deal/price data to SQLite. Used by the dashboard's batch import flow.
        """
        return self.analyze_shopping_notification(notification, persist=True)

    def get_all_price_history(self, limit: int = 100) -> list[dict[str, Any]]:
        """
        Returns all price history records across all products.
        Ordered by most recently observed first.
        """
        with get_db_connection(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT * FROM price_history
                ORDER BY observed_at DESC
                LIMIT ?
                """,
                (limit,),
            )
            return [dict(row) for row in cursor.fetchall()]

    def get_time_sensitive_count(self) -> int:
        """Returns the count of currently time-sensitive deals."""
        with get_db_connection(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT COUNT(*) FROM shopping_deals WHERE is_time_sensitive = 1"
            )
            return cursor.fetchone()[0]
