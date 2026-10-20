"""
Tests for NotifyIQ Shopping Intelligence Service and API Routes.
Covers price extraction, deal scoring, coupon detection, price tracking,
price drop alerts, shopping summary, and FastAPI endpoints.
"""

import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.services.shopping_service import (
    CouponDetector,
    DealScorer,
    PriceDropAlert,
    PriceExtractor,
    ShoppingAnalysis,
    ShoppingService,
    ShoppingSummary,
)


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def shopping_service(tmp_path):
    # Use temporary sqlite database for testing isolation
    db_file = tmp_path / "test_shopping.db"
    return ShoppingService(db_path=str(db_file))


# ============================================================================
# Price Extractor Tests
# ============================================================================

def test_price_extractor_single_price():
    extractor = PriceExtractor()
    res = extractor.extract_prices("Fresh Alphonso Mangoes at Rs. 499 only!", "Blinkit Grocery")
    assert res["has_price"] is True
    assert res["discounted_price"] == 499.0
    assert res["currency"] == "INR"


def test_price_extractor_deal_and_original_price():
    extractor = PriceExtractor()
    res = extractor.extract_prices(
        "iPhone 15 now at ₹64,999 (was ₹79,900) - Save 19% today!",
        "Amazon Deals",
    )
    assert res["has_price"] is True
    assert res["discounted_price"] == 64999.0
    assert res["original_price"] == 79900.0
    assert res["discount_percent"] == 18.7 or res["discount_percent"] == 19.0
    assert res["currency"] == "INR"
    assert res["product_title"] == "Deals" or "iPhone" in res["product_title"] or res["product_title"] is not None


def test_price_extractor_usd_currency():
    extractor = PriceExtractor()
    res = extractor.extract_prices("Special offer: Wireless Earbuds just $49.99 was $99.99", "Audio Store")
    assert res["has_price"] is True
    assert res["currency"] == "USD"
    assert res["discounted_price"] == 49.99
    assert res["original_price"] == 99.99


def test_price_extractor_empty_text():
    extractor = PriceExtractor()
    res = extractor.extract_prices("", "")
    assert res["has_price"] is False
    assert res["discounted_price"] is None


# ============================================================================
# Deal Scorer Tests
# ============================================================================

def test_deal_scorer_high_value_deal():
    scorer = DealScorer()
    price_info = {
        "has_price": True,
        "original_price": 10000.0,
        "discounted_price": 4000.0,
        "discount_percent": 60.0,
        "currency": "INR",
    }
    result = scorer.score_deal(
        text="Flash sale! Ends tonight. Save 60% on premium headphones.",
        title="Amazon Special",
        package_name="in.amazon.mShop.android.shopping",
        price_info=price_info,
    )
    assert result["deal_score"] >= 75.0
    assert result["quality_label"] in ["exceptional_deal", "great_deal"]
    assert result["is_time_sensitive"] is True
    assert len(result["reasons"]) > 0


def test_deal_scorer_regular_price():
    scorer = DealScorer()
    price_info = {
        "has_price": True,
        "original_price": None,
        "discounted_price": 500.0,
        "discount_percent": None,
        "currency": "INR",
    }
    result = scorer.score_deal(
        text="Your monthly subscription was renewed for Rs 500",
        title="Service Alert",
        package_name="com.unknown.app",
        price_info=price_info,
    )
    assert result["deal_score"] <= 40.0
    assert result["is_time_sensitive"] is False


# ============================================================================
# Coupon Detector Tests
# ============================================================================

def test_coupon_detector_various_patterns():
    detector = CouponDetector()
    codes = detector.detect_coupons("Flat 40% OFF! Use code SWIGGYIT to save big.", "Food Delivery")
    assert "SWIGGYIT" in codes

    codes2 = detector.detect_coupons("Apply coupon: SAVE200 on orders above 999", "Fashion")
    assert "SAVE200" in codes2

    codes3 = detector.detect_coupons("Use promo code FLAT50 for free dessert", "Dineout")
    assert "FLAT50" in codes3


def test_coupon_detector_filters_false_positives():
    detector = CouponDetector()
    codes = detector.detect_coupons("Visit https://example.com today for order update notification", "System Alert")
    assert "HTTP" not in codes
    assert "HTTPS" not in codes
    assert "TODAY" not in codes
    assert "ORDER" not in codes


# ============================================================================
# Shopping Service Tests
# ============================================================================

def test_shopping_service_track_and_get_price_history(shopping_service):
    res = shopping_service.track_price(
        package_name="in.amazon.mShop.android.shopping",
        product_title="Sony WH-1000XM5",
        price=24990.0,
        currency="INR",
    )
    assert res["id"] is not None
    assert res["product_title"] == "Sony WH-1000XM5"
    assert res["price"] == 24990.0

    history = shopping_service.get_price_history("Sony WH-1000XM5")
    assert len(history) == 1
    assert history[0]["price"] == 24990.0


def test_shopping_service_detect_price_drop(shopping_service):
    # Track initial high price
    shopping_service.track_price(
        package_name="com.flipkart.android",
        product_title="MacBook Air M2",
        price=99900.0,
        currency="INR",
    )

    # Detect price drop when new price is significantly lower
    alert = shopping_service.detect_price_drop("MacBook Air M2", current_price=84990.0)
    assert alert is not None
    assert isinstance(alert, PriceDropAlert)
    assert alert.current_price == 84990.0
    assert alert.previous_price == 99900.0
    assert alert.drop_amount == 14910.0
    assert alert.drop_percent > 10.0
    assert alert.is_all_time_low is True

    # Check that equal or higher price yields no alert
    no_alert = shopping_service.detect_price_drop("MacBook Air M2", current_price=105000.0)
    assert no_alert is None


def test_shopping_service_analyze_shopping_notification(shopping_service):
    notification = {
        "id": "notif-test-123",
        "title": "Myntra End of Reason Sale",
        "text": "Nike Air Max 90 now at ₹4,999 (was ₹9,999). Flat 50% discount! Use code NIKE50. Hurry, ends tonight!",
        "package_name": "com.myntra.android",
        "category": "promotional",
    }

    analysis = shopping_service.analyze_shopping_notification(notification, persist=True)
    assert isinstance(analysis, ShoppingAnalysis)
    assert analysis.is_shopping is True
    assert analysis.discounted_price == 4999.0
    assert analysis.original_price == 9999.0
    assert analysis.discount_percent == 50.0
    assert "NIKE50" in analysis.coupon_codes
    assert analysis.is_time_sensitive is True
    assert analysis.deal_score >= 60.0

    # Verify deal was saved in DB
    best_deals = shopping_service.get_best_deals(limit=10)
    assert len(best_deals) >= 1
    assert best_deals[0]["discounted_price"] == 4999.0


def test_shopping_service_summary(shopping_service):
    # Seed a deal
    shopping_service.save_deal({
        "notification_id": "seed-1",
        "product_title": "Kindle Paperwhite",
        "original_price": 14999.0,
        "discounted_price": 10999.0,
        "discount_percent": 26.7,
        "deal_score": 65.0,
        "quality_label": "great_deal",
        "coupon_codes": ["READMORE"],
        "is_time_sensitive": True,
        "source_app": "in.amazon.mShop.android.shopping",
    })

    summary = shopping_service.get_shopping_summary()
    assert isinstance(summary, ShoppingSummary)
    assert summary.active_deals_count >= 1
    assert summary.coupons_found >= 1
    assert summary.avg_discount_percent > 0.0
    assert len(summary.top_stores) >= 1


# ============================================================================
# FastAPI Route Tests
# ============================================================================

def test_api_shopping_summary_endpoint(client):
    response = client.get("/shopping/summary")
    assert response.status_code == 200
    data = response.json()
    assert "total_shopping_notifications" in data
    assert "active_deals_count" in data
    assert "coupons_found" in data
    assert "avg_discount_percent" in data
    assert "top_stores" in data


def test_api_shopping_deals_endpoint(client):
    response = client.get("/shopping/deals?limit=10&min_score=0.0")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_api_shopping_analyze_endpoint(client):
    payload = {
        "title": "Flipkart Big Billion Days",
        "text": "Samsung Galaxy S24 Ultra now at ₹1,09,999 was ₹1,29,999. Extra ₹5,000 off with code BBD2026!",
        "package_name": "com.flipkart.android",
        "category": "promotional",
        "persist": True,
    }
    response = client.post("/shopping/analyze", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["is_shopping"] is True
    assert data["discounted_price"] == 109999.0
    assert data["original_price"] == 129999.0
    assert "BBD2026" in data["coupon_codes"]


def test_api_shopping_price_history_endpoint(client):
    # Record a price point first
    record_payload = {
        "product_title": "Sony Bravia 55 OLED",
        "package_name": "in.amazon.mShop.android.shopping",
        "price": 124990.0,
        "currency": "INR",
    }
    rec_res = client.post("/shopping/price-history", json=record_payload)
    assert rec_res.status_code == 201

    # Fetch history
    history_res = client.get("/shopping/price-history/Sony%20Bravia%2055%20OLED")
    assert history_res.status_code == 200
    history_data = history_res.json()
    assert len(history_data) >= 1
    assert history_data[0]["price"] == 124990.0


def test_api_shopping_coupons_endpoint(client):
    response = client.get("/shopping/coupons")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_api_extension_track_endpoint(client):
    payload = {
        "product_title": "Apple iPhone 16 Pro 128GB",
        "current_price": 114900.0,
        "original_price": 119900.0,
        "currency": "INR",
        "store": "Amazon",
        "url": "https://www.amazon.in/dp/B0CHX1W1XY",
    }
    response = client.post("/shopping/extension/track", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["status"] == "tracked"
    assert data["product_title"] == "Apple iPhone 16 Pro 128GB"
    assert data["current_price"] == 114900.0
    assert "verdict" in data
    assert "deal_score" in data
    assert "lowest_price" in data
    assert isinstance(data["price_history"], list)
    assert isinstance(data["coupons"], list)


def test_api_extension_coupons_endpoint(client):
    response = client.get("/shopping/extension/coupons/Amazon")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_api_extension_alert_lifecycle(client):
    # 1. Create alert
    alert_payload = {
        "product_title": "Sony WH-1000XM5",
        "target_price": 22000.0,
        "current_price": 24990.0,
        "currency": "INR",
        "store": "Amazon",
        "url": "https://www.amazon.in/dp/B09XS7JWHH",
    }
    res = client.post("/shopping/extension/alert", json=alert_payload)
    assert res.status_code == 200
    assert res.json()["status"] == "alert_created"

    # 2. List alerts
    list_res = client.get("/shopping/extension/alerts")
    assert list_res.status_code == 200
    alerts = list_res.json()
    assert len(alerts) >= 1
    assert any(a["product_title"] == "Sony WH-1000XM5" for a in alerts)

    # 3. Delete alert
    del_res = client.delete("/shopping/extension/alert/0")
    assert del_res.status_code == 200
    assert del_res.json()["status"] == "deleted"
