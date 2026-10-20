"""
Model training script for NotifyIQ category classifier.
Trains a TF-IDF + Logistic Regression pipeline on reproducible synthetic data.
Saves model artifact to models/category_classifier.joblib and metadata.
"""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
import joblib
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import classification_report, f1_score
from sklearn.model_selection import StratifiedKFold, cross_val_score
from sklearn.pipeline import Pipeline

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from backend.utils.configuration import settings
from backend.utils.logging_config import logger


def train():
    train_csv = BASE_DIR / "data" / "training_notifications.csv"
    if not train_csv.exists():
        print(f"Error: Training dataset not found at {train_csv}. Run generate_sample_data.py first.")
        sys.exit(1)

    df = pd.read_csv(train_csv)
    print(f"Loaded {len(df)} samples from {train_csv}")

    # Combine title and text for training
    df["full_text"] = df["title"].fillna("") + " " + df["text"].fillna("")
    import numpy as np
    X = np.array(df["full_text"].tolist())
    y = np.array(df["ground_truth_category"].tolist())

    pipeline = Pipeline([
        (
            "tfidf",
            TfidfVectorizer(
                ngram_range=(1, 2),
                max_features=4000,
                sublinear_tf=True,
                lowercase=True,
            ),
        ),
        (
            "clf",
            LogisticRegression(
                C=1.5,
                max_iter=1000,
                class_weight="balanced",
                random_state=42,
            ),
        ),
    ])

    print("Evaluating with 5-fold Stratified Cross-Validation...")
    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    f1_scores = cross_val_score(pipeline, X, y, cv=cv, scoring="f1_macro")
    mean_f1 = float(f1_scores.mean())
    std_f1 = float(f1_scores.std())
    print(f"Cross-Validation Macro-F1: {mean_f1:.4f} (+/- {std_f1:.4f})")

    # Fit on all training data
    pipeline.fit(X, y)
    preds = pipeline.predict(X)
    train_f1 = float(f1_score(y, preds, average="macro"))
    print(f"Full Training Macro-F1: {train_f1:.4f}")

    # Ensure models directory exists
    settings.model_dir.mkdir(parents=True, exist_ok=True)

    # Save model artifact
    model_path = settings.classifier_model_path
    joblib.dump(pipeline, model_path)
    print(f"Model artifact saved to: {model_path}")

    # Save metadata
    metadata = {
        "model_type": "tfidf_logistic_regression",
        "trained_at": datetime.now(timezone.utc).isoformat(),
        "training_samples": len(df),
        "classes": list(pipeline.classes_),
        "cv_macro_f1": round(mean_f1, 4),
        "cv_macro_f1_std": round(std_f1, 4),
        "train_macro_f1": round(train_f1, 4),
        "random_seed": 42,
    }
    meta_path = settings.model_metadata_path
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2)
    print(f"Model metadata saved to: {meta_path}")


if __name__ == "__main__":
    train()
