"""
NotifyIQ Smart Shopping Extension.

Intelligent shopping notification analyzer for extracting prices, discounts,
promo codes, and scoring deal quality (BuyHatke-like shopping intelligence).
"""

from backend.ai.shopping.price_extractor import PriceInfo, extract_prices
from backend.ai.shopping.deal_scorer import DealScore, score_deal
from backend.ai.shopping.coupon_detector import CouponInfo, extract_coupons, detect_coupons

__all__ = [
    "PriceInfo",
    "extract_prices",
    "DealScore",
    "score_deal",
    "CouponInfo",
    "extract_coupons",
    "detect_coupons",
]
