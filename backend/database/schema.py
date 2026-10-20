"""
SQLite schema definitions and migration logic for NotifyIQ.
Enforces relational integrity, foreign keys, and indexes.
"""

CURRENT_SCHEMA_VERSION = 1

CREATE_TABLES_SQL = """
-- Schema migration version tracker
CREATE TABLE IF NOT EXISTS schema_migrations (
    version INTEGER PRIMARY KEY,
    applied_at TEXT NOT NULL
);

-- Notification duplicate groups
CREATE TABLE IF NOT EXISTS notification_groups (
    id TEXT PRIMARY KEY,
    fingerprint TEXT NOT NULL,
    grouping_method TEXT NOT NULL,
    similarity_threshold REAL,
    created_at TEXT NOT NULL
);

-- Core notifications table
CREATE TABLE IF NOT EXISTS notifications (
    id TEXT PRIMARY KEY,
    event_id TEXT UNIQUE NOT NULL,
    package_name TEXT NOT NULL,
    title TEXT,
    text TEXT,
    normalized_text TEXT,
    category TEXT NOT NULL,
    category_confidence REAL NOT NULL,
    model_type TEXT NOT NULL,
    priority_score REAL NOT NULL,
    priority_level TEXT NOT NULL,
    urgency_score REAL NOT NULL,
    action_score REAL NOT NULL,
    deadline_score REAL NOT NULL,
    importance_score REAL NOT NULL,
    recency_score REAL NOT NULL,
    action_detected INTEGER NOT NULL DEFAULT 0,
    action_type TEXT,
    action_text TEXT,
    deadline_text TEXT,
    deadline_at TEXT,
    deadline_status TEXT NOT NULL DEFAULT 'none',
    priority_reasons TEXT NOT NULL DEFAULT '[]',
    duplicate_group_id TEXT,
    is_duplicate INTEGER NOT NULL DEFAULT 0,
    received_at TEXT NOT NULL,
    processed_at TEXT NOT NULL,
    retention_expires_at TEXT,
    is_read INTEGER NOT NULL DEFAULT 0,
    FOREIGN KEY (duplicate_group_id) REFERENCES notification_groups(id) ON DELETE SET NULL
);

-- Actions detected from notifications
CREATE TABLE IF NOT EXISTS actions (
    id TEXT PRIMARY KEY,
    notification_id TEXT NOT NULL,
    action_type TEXT NOT NULL,
    action_text TEXT NOT NULL,
    deadline_at TEXT,
    status TEXT NOT NULL DEFAULT 'open',
    created_at TEXT NOT NULL,
    completed_at TEXT,
    FOREIGN KEY (notification_id) REFERENCES notifications(id) ON DELETE CASCADE
);

-- User feedback for active learning and model tuning
CREATE TABLE IF NOT EXISTS feedback (
    id TEXT PRIMARY KEY,
    notification_id TEXT NOT NULL,
    feedback_type TEXT NOT NULL,
    original_value TEXT NOT NULL,
    corrected_value TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY (notification_id) REFERENCES notifications(id) ON DELETE CASCADE
);

-- Key-value persistent application settings
CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_notifications_event_id ON notifications(event_id);
CREATE INDEX IF NOT EXISTS idx_notifications_category ON notifications(category);
CREATE INDEX IF NOT EXISTS idx_notifications_priority_level ON notifications(priority_level);
CREATE INDEX IF NOT EXISTS idx_notifications_received_at ON notifications(received_at);
CREATE INDEX IF NOT EXISTS idx_notifications_duplicate_group ON notifications(duplicate_group_id);
CREATE INDEX IF NOT EXISTS idx_notifications_package_name ON notifications(package_name);
CREATE INDEX IF NOT EXISTS idx_actions_notification_id ON actions(notification_id);
CREATE INDEX IF NOT EXISTS idx_actions_status ON actions(status);
CREATE INDEX IF NOT EXISTS idx_feedback_notification_id ON feedback(notification_id);
"""
