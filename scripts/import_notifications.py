"""
Notification batch import script for NotifyIQ.
Imports Android-generated JSON notifications, validates records,
runs them through the AI pipeline, and persists them into SQLite.
Usage:
    python scripts/import_notifications.py --file data/sample_notifications.json
"""

import argparse
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from backend.ai.pipeline import AIPipeline
from backend.database.repository import Repository
from backend.services.import_service import ImportService


def main():
    parser = argparse.ArgumentParser(description="Import notification JSON into NotifyIQ")
    parser.add_argument(
        "--file",
        type=str,
        default="data/sample_notifications.json",
        help="Path to JSON notification file",
    )
    args = parser.parse_args()

    file_path = Path(args.file)
    if not file_path.is_absolute():
        file_path = BASE_DIR / file_path

    if not file_path.exists():
        print(f"Error: File not found: {file_path}")
        sys.exit(1)

    print(f"Reading notification events from {file_path}...")
    repo = Repository()
    import_service = ImportService(repository=repo)
    report = import_service.import_file(file_path)

    print(f"\nImport Validation Summary:")
    print(f"  Total records inspected:  {report.total_records}")
    print(f"  Accepted for processing:  {report.accepted_count}")
    print(f"  Rejected (invalid):       {report.rejected_count}")
    print(f"  Already processed (skip): {report.already_processed_count}")

    if report.rejected_records:
        print("\nRejected records details:")
        for r in report.rejected_records[:5]:
            print(f"  - {r.get('event_id', 'unknown')}: {r.get('reason')}")

    if report.accepted_records:
        print(f"\nProcessing {report.accepted_count} accepted notifications through AI Pipeline...")
        pipeline = AIPipeline(repository=repo)
        for idx, event in enumerate(report.accepted_records, 1):
            pipeline.process_notification(event, persist=True)

        print(f"Successfully processed and stored {report.accepted_count} notifications.")


if __name__ == "__main__":
    main()
