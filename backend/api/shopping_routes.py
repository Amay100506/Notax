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
