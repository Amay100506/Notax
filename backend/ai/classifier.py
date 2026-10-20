"""
Classification Engine for NotifyIQ.
Uses TF-IDF + Logistic Regression with reproducible model persistence and loading.
Includes deterministic rule-based fallback when model artifact is unavailable.
"""

import json
from pathlib import Path
from typing import Optional
import joblib
from pydantic import BaseModel
from backend.utils.configuration import settings
from backend.utils.logging_config import logger

CATEGORIES = [
    "action_required",
    "transactional",
    "social",
    "promotional",
    "system",
    "unknown",
]


class ClassificationResult(BaseModel):
    category: str
    confidence: float
    model_type: str
    needs_review: bool


class CategoryClassifier:
    def __init__(self, model_path: Optional[Path] = None):
        self.model_path = model_path or settings.classifier_model_path
        self.model = None
        self.metadata = {}
        self.load_model()

    def load_model(self) -> bool:
        """Attempts to load pre-trained scikit-learn pipeline from disk."""
        if self.model_path and Path(self.model_path).exists():
            try:
                self.model = joblib.load(self.model_path)
                meta_path = settings.model_metadata_path
                if meta_path.exists():
                    with open(meta_path, "r", encoding="utf-8") as f:
                        self.metadata = json.load(f)
                logger.info("Loaded classifier model from %s", self.model_path)
                return True
            except Exception as e:
                logger.warning("Failed to load model from %s (%s). Falling back to rule-based classifier.", self.model_path, str(e))
                self.model = None
                return False
        else:
            logger.info("No model found at %s. Using rule-based fallback classifier.", self.model_path)
            self.model = None
            return False

    def predict(self, text: str, title: str = "", package_name: str = "") -> ClassificationResult:
        """
        Classifies notification text into one of six categories.
        Uses ML pipeline if available, otherwise deterministic rule fallback.
        """
        combined = f"{title} {text}".strip()
        if not combined:
            return ClassificationResult(
                category="unknown",
                confidence=1.0,
                model_type="empty_text_rule",
                needs_review=False,
            )

        # 1. If trained ML model is available, use it
        if self.model is not None:
            try:
                # Expect pipeline with predict_proba
                probs = self.model.predict_proba([combined])[0]
                classes = list(self.model.classes_)
                best_idx = probs.argmax()
                best_class = classes[best_idx]
                confidence = float(probs[best_idx])
                needs_review = confidence < settings.confidence_threshold

                # If confidence is exceptionally low, categorize as unknown
                if confidence < 0.35 and best_class != "unknown":
                    best_class = "unknown"
                    needs_review = True

                return ClassificationResult(
                    category=best_class,
                    confidence=round(confidence, 3),
                    model_type="tfidf_logistic_regression",
                    needs_review=needs_review,
                )
            except Exception as e:
                logger.warning("ML inference failed (%s); reverting to rule fallback.", str(e))

        # 2. Deterministic Rule-Based Fallback
        return self._rule_based_classify(combined, package_name)

    def _rule_based_classify(self, text: str, package_name: str = "") -> ClassificationResult:
        """Deterministic keyword fallback classifier."""
        t = text.lower()
        pkg = package_name.lower()

        # Promotional indicators
        if any(w in t for w in ["% off", "flash sale", "discount", "promo", "deal", "coupon", "clearance", "buy 1 get 1", "free delivery", "cashback"]):
            return ClassificationResult(
                category="promotional",
                confidence=0.82,
                model_type="rule_fallback",
                needs_review=False,
            )

        # Action-required indicators
        if any(w in t for w in ["please submit", "please review", "approve", "verify your", "action needed", "action required", "rsvp", "due tomorrow", "due by", "complete the"]):
            return ClassificationResult(
                category="action_required",
                confidence=0.85,
                model_type="rule_fallback",
                needs_review=False,
            )

        # Transactional indicators
        if any(w in t for w in ["debited", "credited", "shipped", "out for delivery", "delivered", "receipt", "pnr", "boarding pass", "booking confirmed", "invoice", "refund"]) or any(p in pkg for p in ["bank", "shopping", "pay", "amazon", "swiggy", "zomato"]):
            return ClassificationResult(
                category="transactional",
                confidence=0.80,
                model_type="rule_fallback",
                needs_review=False,
            )

        # Social indicators
        if any(w in t for w in ["liked your", "commented on", "mentioned you", "sent a message", "connection request", "new snap", "react to"]) or any(p in pkg for p in ["whatsapp", "instagram", "twitter", "facebook", "linkedin", "telegram", "discord", "signal"]):
            return ClassificationResult(
                category="social",
                confidence=0.78,
                model_type="rule_fallback",
                needs_review=False,
            )

        # System indicators
        if any(w in t for w in ["battery", "system update", "security alert", "connected to", "storage space", "download complete", "gps active"]) or "android" in pkg:
            return ClassificationResult(
                category="system",
                confidence=0.80,
                model_type="rule_fallback",
                needs_review=False,
            )

        # Unknown fallback
        return ClassificationResult(
            category="unknown",
            confidence=0.50,
            model_type="rule_fallback",
            needs_review=True,
        )
