"""
Database connection manager and schema initialization.
"""

import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Generator
from backend.utils.configuration import settings
from backend.utils.logging_config import logger
from backend.database.schema import CREATE_TABLES_SQL, CURRENT_SCHEMA_VERSION


def get_db_path() -> Path:
    """Returns the resolved Path object for the database."""
    db_path = Path(settings.db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    return db_path


def init_db(db_path: Path | str | None = None) -> None:
    """
    Initializes the SQLite database schema if not already initialized.
    Checks and records the schema version.
    """
    path = Path(db_path) if db_path else get_db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    
    conn = sqlite3.connect(path)
    try:
        conn.execute("PRAGMA foreign_keys = ON;")
        conn.executescript(CREATE_TABLES_SQL)
        
        # Check migration version
        cursor = conn.cursor()
        cursor.execute("SELECT version FROM schema_migrations WHERE version = ?", (CURRENT_SCHEMA_VERSION,))
        row = cursor.fetchone()
        if not row:
            now_iso = datetime.now(timezone.utc).isoformat()
            cursor.execute(
                "INSERT INTO schema_migrations (version, applied_at) VALUES (?, ?)",
                (CURRENT_SCHEMA_VERSION, now_iso)
            )
            conn.commit()
            logger.info("Database schema initialized at version %d (db=%s)", CURRENT_SCHEMA_VERSION, path.name)
        else:
            logger.debug("Database schema already up-to-date at version %d", CURRENT_SCHEMA_VERSION)
    finally:
        conn.close()


@contextmanager
def get_db_connection(db_path: Path | str | None = None) -> Generator[sqlite3.Connection, None, None]:
    """
    Context manager providing a SQLite connection with foreign keys enabled
    and row factory set to sqlite3.Row for dictionary-like access.
    """
    path = Path(db_path) if db_path else get_db_path()
    conn = sqlite3.connect(path)
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()
