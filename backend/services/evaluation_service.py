"""
Evaluation Service for NotifyIQ.
Evaluates category classification, action detection, deadline extraction,
and priority scoring against ground-truth labeled held-out data.
Computes precision, recall, macro-F1, confusion matrix, and latency benchmarks.
"""

import time
import numpy as np
import pandas as pd
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix, f1_score, precision_recall_fscore_support
from backend.ai.classifier import CategoryClassifier
from backend.ai.pipeline import AIPipeline
from backend.utils.configuration import settings
from backend.utils.logging_config import logger


class EvaluationService:
    def __init__(self, pipeline: Optional[AIPipeline] = None):
        self.pipeline = pipeline or AIPipeline()

    def evaluate_dataset(self, csv_path: Path | str) -> dict[str, Any]:
        """
        Runs comprehensive evaluation against a labeled evaluation dataset CSV.
        Returns a serializable dictionary with all metrics.
        """
        df = pd.read_csv(csv_path)
        logger.info("Evaluating %d test samples from %s", len(df), csv_path)

        latencies_ms: list[float] = []
        pred_categories: list[str] = []
        pred_priorities: list[str] = []
        pred_actions: list[bool] = []
        pred_deadlines: list[bool] = []

        # Baseline predictions (rules-only baseline)
        baseline_clf = CategoryClassifier(model_path=Path("non_existent_baseline.joblib"))
        baseline_categories: list[str] = []

        for _, row in df.iterrows():
            event = {
                "event_id": str(row.get("event_id", "")),
                "package_name": str(row.get("package_name", "")),
                "title": str(row.get("title", "")) if pd.notna(row.get("title")) else "",
                "text": str(row.get("text", "")) if pd.notna(row.get("text")) else "",
                "posted_at": str(row.get("posted_at", datetime.now(timezone.utc).isoformat())),
            }

            # Measure processing latency
            t0 = time.perf_counter()
            res = self.pipeline.process_notification(event, persist=False)
            t1 = time.perf_counter()
            latencies_ms.append((t1 - t0) * 1000.0)

            pred_categories.append(res["category"])
            pred_priorities.append(res["priority_level"])
            pred_actions.append(bool(res["action_detected"]))
            pred_deadlines.append(res["deadline_status"] in ["resolved", "unresolved"])

            # Baseline prediction
            base_res = baseline_clf.predict(event["text"], title=event["title"], package_name=event["package_name"])
            baseline_categories.append(base_res.category)

        # Ground truth series
        y_true_cat = df["ground_truth_category"].astype(str).tolist()
        y_true_prio = df["ground_truth_priority"].astype(str).tolist()
        y_true_act = df["ground_truth_has_action"].astype(bool).tolist()
        y_true_dl = df["ground_truth_has_deadline"].astype(bool).tolist()

        # Category Classification Metrics
        labels = sorted(list(set(y_true_cat + pred_categories)))
        acc = float(accuracy_score(y_true_cat, pred_categories))
        macro_f1 = float(f1_score(y_true_cat, pred_categories, average="macro", zero_division=0))
        prec, rec, f1s, support = precision_recall_fscore_support(y_true_cat, pred_categories, labels=labels, zero_division=0)
        cm = confusion_matrix(y_true_cat, pred_categories, labels=labels).tolist()

        per_class_metrics = {}
        for idx, lbl in enumerate(labels):
            per_class_metrics[lbl] = {
                "precision": round(float(prec[idx]), 3),
                "recall": round(float(rec[idx]), 3),
                "f1": round(float(f1s[idx]), 3),
                "support": int(support[idx]),
            }

        # Baseline Comparison
        base_acc = float(accuracy_score(y_true_cat, baseline_categories))
        base_f1 = float(f1_score(y_true_cat, baseline_categories, average="macro", zero_division=0))

        # High-Priority Detection Metrics
        y_true_high = [1 if p == "high" else 0 for p in y_true_prio]
        y_pred_high = [1 if p == "high" else 0 for p in pred_priorities]
        p_high, r_high, f1_high, _ = precision_recall_fscore_support(y_true_high, y_pred_high, average="binary", zero_division=0)

        # Action Detection Metrics
        p_act, r_act, f1_act, _ = precision_recall_fscore_support(y_true_act, pred_actions, average="binary", zero_division=0)

        # Deadline Detection Metrics
        p_dl, r_dl, f1_dl, _ = precision_recall_fscore_support(y_true_dl, pred_deadlines, average="binary", zero_division=0)

        # Latency statistics
        lat_arr = np.array(latencies_ms)
        median_lat = float(np.median(lat_arr))
        p95_lat = float(np.percentile(lat_arr, 95))
        mean_lat = float(np.mean(lat_arr))

        report = {
            "evaluated_at": datetime.now(timezone.utc).isoformat(),
            "evaluation_dataset": str(csv_path),
            "sample_count": len(df),
            "category_classification": {
                "accuracy": round(acc, 4),
                "macro_f1": round(macro_f1, 4),
                "labels": labels,
                "per_class": per_class_metrics,
                "confusion_matrix": cm,
            },
            "baseline_comparison": {
                "baseline_name": "Keyword Rules Baseline",
                "baseline_accuracy": round(base_acc, 4),
                "baseline_macro_f1": round(base_f1, 4),
                "notifyiq_macro_f1": round(macro_f1, 4),
                "macro_f1_improvement": round(macro_f1 - base_f1, 4),
            },
            "high_priority_detection": {
                "precision": round(float(p_high), 4),
                "recall": round(float(r_high), 4),
                "f1": round(float(f1_high), 4),
            },
            "action_extraction": {
                "precision": round(float(p_act), 4),
                "recall": round(float(r_act), 4),
                "f1": round(float(f1_act), 4),
            },
            "deadline_extraction": {
                "precision": round(float(p_dl), 4),
                "recall": round(float(r_dl), 4),
                "f1": round(float(f1_dl), 4),
            },
            "latency_ms": {
                "median": round(median_lat, 2),
                "p95": round(p95_lat, 2),
                "mean": round(mean_lat, 2),
            },
        }

        return report
