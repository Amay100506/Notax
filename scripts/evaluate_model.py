"""
Model evaluation script for NotifyIQ.
Runs the evaluation service against held-out data/evaluation_notifications.csv
and saves the benchmark results to models/evaluation_report.json.
"""

import json
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from backend.services.evaluation_service import EvaluationService
from backend.utils.configuration import settings


def main():
    eval_csv = BASE_DIR / "data" / "evaluation_notifications.csv"
    if not eval_csv.exists():
        print(f"Error: Evaluation dataset not found at {eval_csv}. Run generate_sample_data.py first.")
        sys.exit(1)

    print(f"Evaluating NotifyIQ model against {eval_csv}...")
    service = EvaluationService()
    report = service.evaluate_dataset(eval_csv)

    cat_metrics = report["category_classification"]
    base_comp = report["baseline_comparison"]
    high_prio = report["high_priority_detection"]
    lat = report["latency_ms"]

    print("\n" + "=" * 50)
    print("NOTIFYIQ MODEL EVALUATION REPORT")
    print("=" * 50)
    print(f"Sample Count: {report['sample_count']}")
    print(f"Category Accuracy: {cat_metrics['accuracy']:.4f}")
    print(f"Category Macro-F1: {cat_metrics['macro_f1']:.4f}")
    print(f"Baseline Macro-F1: {base_comp['baseline_macro_f1']:.4f}")
    print(f"Improvement Over Baseline: +{base_comp['macro_f1_improvement']:.4f}")
    print(f"High-Priority Precision: {high_prio['precision']:.4f}")
    print(f"High-Priority Recall:    {high_prio['recall']:.4f}")
    print(f"Action Detection F1:     {report['action_extraction']['f1']:.4f}")
    print(f"Deadline Extraction F1:  {report['deadline_extraction']['f1']:.4f}")
    print(f"Processing Latency:      Median {lat['median']} ms | P95 {lat['p95']} ms")
    print("=" * 50)

    # Save to models/evaluation_report.json
    out_file = settings.evaluation_report_path
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)
    print(f"Detailed evaluation report saved to: {out_file}")


if __name__ == "__main__":
    main()
