"""
Database initialization script for NotifyIQ.
Creates tables, sets up schema migrations, and prepares database for operation.
"""

import sys
from pathlib import Path

# Ensure project root is on sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from backend.database.connection import init_db, get_db_path


def main():
    db_file = get_db_path()
    print(f"Initializing NotifyIQ database at: {db_file}")
    init_db(db_file)
    print("Database schema successfully initialized with tables:")
    print("  - notifications")
    print("  - actions")
    print("  - feedback")
    print("  - notification_groups")
    print("  - settings")
    print("  - schema_migrations")


if __name__ == "__main__":
    main()
