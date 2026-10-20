"""
FastAPI Routes for Shopping Intelligence.
Provides REST endpoints for shopping analytics, deals discovery,
price history tracking, coupon codes, and notification shopping analysis.
"""

from typing import Any, Optional
from fastapi import APIRouter, Body, HTTPException, Query, status
from pydantic import BaseModel, Field

from backend.services.shopping_service import (
    PriceDropAlert,
    ShoppingAnalysis,
    ShoppingService,
    ShoppingSummary,
    TopStore,
)
from backend.utils.logging_config import logger

router = APIRouter(prefix="/shopping", tags=["Shopping Intelligence"])
shopping_service = ShoppingService()


# ============================================================================
# Request & Response Schemas
# ============================================================================

class ShoppingNotificationRequest(BaseModel):
    """Payload to analyze a notification for shopping deals, prices, and coupons."""
    id: Optional[str] = Field(default=None, description="Optional notification ID")
    title: Optional[str] = Field(default="", description="Notification title")
    text: Optional[str] = Field(default="", description="Notification body text")
    package_name: Optional[str] = Field(default="unknown.shopping", description="Source app package name")
    category: Optional[str] = Field(default="promotional", description="Category classification")
    persist: bool = Field(default=False, description="Whether to persist detected deals and prices")

    model_config = {"extra": "allow"}


class TrackPriceRequest(BaseModel):
    """Manual price point recording request."""
    product_title: str
    package_name: str
    price: float
    currency: str = "INR"
    notification_id: Optional[str] = None


class ExtensionTrackRequest(BaseModel):
    """Payload received from the BuyHatke browser extension."""
    product_title: str
    current_price: float
    original_price: Optional[float] = None
    currency: str = "INR"
    store: str = "Amazon"
    url: Optional[str] = None
    sku: Optional[str] = None


# ============================================================================
# Endpoints
# ============================================================================

@router.get("/summary", response_model=ShoppingSummary)
def get_shopping_summary():
    """
    Returns aggregated shopping intelligence metrics:
    total shopping notifications, active deals count, coupons harvested,
    average discount percentage, top stores, and detected price drops.
    """
    try:
        return shopping_service.get_shopping_summary()
    except Exception as e:
        logger.error("Failed to generate shopping summary: %s", str(e), exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to retrieve shopping summary")


@router.get("/deals")
def list_best_deals(
    limit: int = Query(default=50, ge=1, le=200, description="Max deals to return"),
    min_score: float = Query(default=0.0, ge=0.0, le=100.0, description="Minimum deal score threshold"),
):
    """
    Returns curated active deals sorted by AI deal score descending.
    Allows filtering by minimum quality score.
    """
    try:
        return shopping_service.get_best_deals(limit=limit, min_score=min_score)
    except Exception as e:
        logger.error("Failed to fetch shopping deals: %s", str(e), exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to fetch deals")


@router.get("/price-history/{product_title}")
def get_price_history(
    product_title: str,
    limit: int = Query(default=50, ge=1, le=200, description="Max observations to return"),
):
    """
    Returns historical price observations for a given product title.
    Supports exact and substring title matches.
    """
    try:
        clean_title = product_title.strip()
        if not clean_title:
            raise HTTPException(status_code=400, detail="Product title cannot be empty")
        return shopping_service.get_price_history(product_title=clean_title, limit=limit)
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to fetch price history for '%s': %s", product_title, str(e), exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to fetch price history")


@router.post("/analyze", response_model=ShoppingAnalysis)
def analyze_notification(req: ShoppingNotificationRequest):
    """
    Analyzes a notification for shopping intelligence:
    - Extracts original and discounted prices
    - Calculates deal score and quality label
    - Detects promo / coupon codes
    - Compares against historical pricing for price drop alerts
    - Optionally persists observed deal and prices
    """
    try:
        payload = req.model_dump()
        return shopping_service.analyze_shopping_notification(notification=payload, persist=req.persist)
    except Exception as e:
        logger.error("Failed to analyze shopping notification: %s", str(e), exc_info=True)
        raise HTTPException(status_code=500, detail=f"Shopping analysis failed: {str(e)}")


@router.get("/coupons")
def list_coupons():
    """
    Returns all detected coupon codes and promotional vouchers
    harvested from shopping notifications.
    """
    try:
        return shopping_service.get_all_coupons()
    except Exception as e:
        logger.error("Failed to list coupons: %s", str(e), exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to list coupon codes")


@router.post("/price-history", status_code=status.HTTP_201_CREATED)
def record_price(req: TrackPriceRequest):
    """
    Directly records an observed product price point in historical tracking.
    """
    try:
        return shopping_service.track_price(
            package_name=req.package_name,
            product_title=req.product_title,
            price=req.price,
            currency=req.currency,
            notification_id=req.notification_id,
        )
    except Exception as e:
        logger.error("Failed to record price observation: %s", str(e), exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to record price observation")


# ============================================================================
# BuyHatke Extension Support Endpoints
# ============================================================================

@router.post("/extension/track", status_code=status.HTTP_201_CREATED)
def extension_track_product(req: ExtensionTrackRequest):
    """
    Receives live product metadata from the BuyHatke browser extension,
    records historical price point, and returns comparison insights & coupons.
    """
    try:
        store_pkg = f"com.{req.store.lower().replace(' ', '')}.android"
        
        # 1. Record current price observation
        price_record = shopping_service.track_price(
            package_name=store_pkg,
            product_title=req.product_title,
            price=req.current_price,
            currency=req.currency,
        )

        # 2. Check for price drop
        price_drop = shopping_service.detect_price_drop(req.product_title, req.current_price)

        # 3. Retrieve price history
        history = shopping_service.get_price_history(req.product_title, limit=30)
        prices = [float(h["price"]) for h in history] if history else [req.current_price]
        lowest = min(prices)
        highest = max(prices)
        avg_price = sum(prices) / len(prices)

        # 4. Score the current deal
        price_info = {
            "has_price": True,
            "original_price": req.original_price or highest,
            "discounted_price": req.current_price,
            "current_price": req.current_price,
            "discount_percent": round(((highest - req.current_price) / highest) * 100, 1) if highest > req.current_price else 0.0,
            "currency": req.currency,
        }
        deal_scored = shopping_service.deal_scorer.score_deal(
            text=f"{req.product_title} at {req.current_price}",
            title=req.product_title,
            package_name=store_pkg,
            price_info=price_info,
        )

        # 5. Fetch available coupons for this store
        all_coupons = shopping_service.get_all_coupons()
        matching_coupons = [
            c for c in all_coupons
            if req.store.lower() in str(c.get("source_app", "")).lower()
               or req.store.lower() in str(c.get("product_title", "")).lower()
        ]
        # If no store-specific coupon, offer global coupons
        if not matching_coupons:
            matching_coupons = all_coupons[:3]

        # Determine verdict
        if req.current_price <= lowest and len(prices) > 1:
            verdict = "🔥 Lowest Recorded Price! Best time to buy."
        elif price_drop:
            verdict = f"📉 Price dropped by {price_drop.drop_percent:.0f}%! Good deal."
        elif req.current_price < avg_price:
            verdict = "✨ Price is below historical average."
        elif req.current_price > avg_price and len(prices) > 1:
            verdict = "⚠️ Price is currently higher than average. You may want to wait."
        else:
            verdict = "📦 Price is steady."

        return {
            "status": "tracked",
            "product_title": req.product_title,
            "store": req.store,
            "current_price": req.current_price,
            "currency": req.currency,
            "lowest_price": lowest,
            "highest_price": highest,
            "average_price": round(avg_price, 2),
            "deal_score": deal_scored.get("deal_score", 50.0),
            "quality_label": deal_scored.get("quality_label", "good_deal"),
            "is_time_sensitive": deal_scored.get("is_time_sensitive", False),
            "verdict": verdict,
            "price_drop": price_drop.model_dump() if price_drop else None,
            "price_history": history,
            "coupons": matching_coupons,
        }
    except Exception as e:
        logger.error("Failed to process extension track: %s", str(e), exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to process product tracking")


@router.get("/extension/coupons/{store_name}")
def extension_get_coupons(store_name: str):
    """Returns available coupon codes for a specific shopping site."""
    try:
        all_coupons = shopping_service.get_all_coupons()
        matched = [
            c for c in all_coupons
            if store_name.lower() in str(c.get("source_app", "")).lower()
               or store_name.lower() in str(c.get("product_title", "")).lower()
        ]
        return matched if matched else all_coupons[:5]
    except Exception as e:
        logger.error("Failed to fetch extension coupons: %s", str(e), exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to fetch coupons")
