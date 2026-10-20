"""
Repository layer for parameterized database operations.
Includes notifications, actions, duplicate groups, feedback, settings, and analytics.
"""

import json
import sqlite3
import uuid
from datetime import datetime, timezone
from typing import Any, Optional
from backend.database.connection import get_db_connection


class Repository:
    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path

    # ---------------------------------------------------------
    # NOTIFICATIONS
    # ---------------------------------------------------------

    def create_notification(self, data: dict[str, Any]) -> dict[str, Any]:
        """
        Inserts a processed notification into the database.
        Returns the inserted record dict.
        """
        record_id = data.get("id") or str(uuid.uuid4())
        processed_at = data.get("processed_at") or datetime.now(timezone.utc).isoformat()
        priority_reasons_json = (
            json.dumps(data.get("priority_reasons", []))
            if isinstance(data.get("priority_reasons"), list)
            else (data.get("priority_reasons") or "[]")
        )

        with get_db_connection(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO notifications (
                    id, event_id, package_name, title, text, normalized_text,
                    category, category_confidence, model_type,
                    priority_score, priority_level,
                    urgency_score, action_score, deadline_score, importance_score, recency_score,
                    action_detected, action_type, action_text,
                    deadline_text, deadline_at, deadline_status,
                    priority_reasons, duplicate_group_id, is_duplicate,
                    received_at, processed_at, retention_expires_at, is_read
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record_id,
                    data["event_id"],
                    data["package_name"],
                    data.get("title"),
                    data.get("text"),
                    data.get("normalized_text"),
                    data["category"],
                    float(data.get("category_confidence", 0.0)),
                    data.get("model_type", "unknown"),
                    float(data.get("priority_score", 0.0)),
                    data.get("priority_level", "low"),
                    float(data.get("urgency_score", 0.0)),
                    float(data.get("action_score", 0.0)),
                    float(data.get("deadline_score", 0.0)),
                    float(data.get("importance_score", 0.0)),
                    float(data.get("recency_score", 0.0)),
                    1 if data.get("action_detected") else 0,
                    data.get("action_type"),
                    data.get("action_text"),
                    data.get("deadline_text"),
                    data.get("deadline_at"),
                    data.get("deadline_status", "none"),
                    priority_reasons_json,
                    data.get("duplicate_group_id"),
                    1 if data.get("is_duplicate") else 0,
                    data["received_at"],
                    processed_at,
                    data.get("retention_expires_at"),
                    1 if data.get("is_read") else 0,
                ),
            )

            # If an action was detected, create an action entry linked to this notification
            if data.get("action_detected") and data.get("action_text"):
                action_id = str(uuid.uuid4())
                cursor.execute(
                    """
                    INSERT INTO actions (
                        id, notification_id, action_type, action_text, deadline_at, status, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        action_id,
                        record_id,
                        data.get("action_type", "task"),
                        data["action_text"],
                        data.get("deadline_at"),
                        "open",
                        processed_at,
                    ),
                )

            conn.commit()

        return self.get_notification_by_id(record_id)  # type: ignore

    def get_notification_by_id(self, notification_id: str) -> Optional[dict[str, Any]]:
        with get_db_connection(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM notifications WHERE id = ?", (notification_id,))
            row = cursor.fetchone()
            if not row:
                return None
            res = dict(row)
            res["priority_reasons"] = json.loads(res.get("priority_reasons") or "[]")
            res["action_detected"] = bool(res.get("action_detected"))
            res["is_duplicate"] = bool(res.get("is_duplicate"))
            res["is_read"] = bool(res.get("is_read"))
            return res

    def get_notification_by_event_id(self, event_id: str) -> Optional[dict[str, Any]]:
        with get_db_connection(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM notifications WHERE event_id = ?", (event_id,))
            row = cursor.fetchone()
            if not row:
                return None
            res = dict(row)
            res["priority_reasons"] = json.loads(res.get("priority_reasons") or "[]")
            res["action_detected"] = bool(res.get("action_detected"))
            res["is_duplicate"] = bool(res.get("is_duplicate"))
            res["is_read"] = bool(res.get("is_read"))
            return res

    def list_notifications(
        self,
        limit: int = 50,
        offset: int = 0,
        category: Optional[str] = None,
        priority_level: Optional[str] = None,
        package_name: Optional[str] = None,
        action_detected: Optional[bool] = None,
        deadline_detected: Optional[bool] = None,
        is_duplicate: Optional[bool] = None,
        search: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        is_unread: Optional[bool] = None,
        needs_review: Optional[bool] = None,
        confidence_threshold: float = 0.60,
    ) -> tuple[list[dict[str, Any]], int]:
        """
        Returns a paginated list of notifications matching filters,
        along with the total matching count.
        """
        conditions = []
        params: list[Any] = []

        if category:
            conditions.append("category = ?")
            params.append(category)
        if priority_level:
            conditions.append("priority_level = ?")
            params.append(priority_level)
        if package_name:
            conditions.append("package_name = ?")
            params.append(package_name)
        if action_detected is not None:
            conditions.append("action_detected = ?")
            params.append(1 if action_detected else 0)
        if deadline_detected is not None:
            if deadline_detected:
                conditions.append("deadline_status IN ('resolved', 'unresolved')")
            else:
                conditions.append("deadline_status = 'none'")
        if is_duplicate is not None:
            conditions.append("is_duplicate = ?")
            params.append(1 if is_duplicate else 0)
        if search:
            conditions.append("(title LIKE ? OR text LIKE ? OR package_name LIKE ?)")
            search_param = f"%{search}%"
            params.extend([search_param, search_param, search_param])
        if start_date:
            conditions.append("received_at >= ?")
            params.append(start_date)
        if end_date:
            conditions.append("received_at <= ?")
            params.append(end_date)
        if is_unread is not None:
            conditions.append("is_read = ?")
            params.append(0 if is_unread else 1)
        if needs_review is not None:
            if needs_review:
                conditions.append("category_confidence < ?")
            else:
                conditions.append("category_confidence >= ?")
            params.append(confidence_threshold)

        where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""

        with get_db_connection(self.db_path) as conn:
            cursor = conn.cursor()
            count_query = f"SELECT COUNT(*) FROM notifications {where_clause}"
            cursor.execute(count_query, params)
            total_count = cursor.fetchone()[0]

            data_query = f"""
                SELECT * FROM notifications
                {where_clause}
                ORDER BY priority_score DESC, received_at DESC
                LIMIT ? OFFSET ?
            """
            cursor.execute(data_query, params + [limit, offset])
            rows = cursor.fetchall()

            results = []
            for row in rows:
                item = dict(row)
                item["priority_reasons"] = json.loads(item.get("priority_reasons") or "[]")
                item["action_detected"] = bool(item.get("action_detected"))
                item["is_duplicate"] = bool(item.get("is_duplicate"))
                item["is_read"] = bool(item.get("is_read"))
                results.append(item)

            return results, total_count

    def delete_notification(self, notification_id: str) -> bool:
        """Deletes a notification and cascades to actions/feedback."""
        with get_db_connection(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM notifications WHERE id = ?", (notification_id,))
            conn.commit()
            return cursor.rowcount > 0

    def mark_notification_read(self, notification_id: str, is_read: bool = True) -> bool:
        with get_db_connection(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE notifications SET is_read = ? WHERE id = ?",
                (1 if is_read else 0, notification_id),
            )
            conn.commit()
            return cursor.rowcount > 0

    # ---------------------------------------------------------
    # ACTIONS
    # ---------------------------------------------------------

    def list_actions(
        self,
        status: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        with get_db_connection(self.db_path) as conn:
            cursor = conn.cursor()
            query = """
                SELECT a.*, n.title as notification_title, n.package_name, n.priority_score, n.priority_level
                FROM actions a
                JOIN notifications n ON a.notification_id = n.id
            """
            params: list[Any] = []
            if status:
                query += " WHERE a.status = ?"
                params.append(status)
            query += " ORDER BY a.deadline_at ASC NULLS LAST, a.created_at DESC LIMIT ? OFFSET ?"
            params.extend([limit, offset])

            cursor.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]

    def update_action_status(self, action_id: str, status: str) -> bool:
        completed_at = datetime.now(timezone.utc).isoformat() if status == "completed" else None
        with get_db_connection(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE actions SET status = ?, completed_at = ? WHERE id = ?",
                (status, completed_at, action_id),
            )
            conn.commit()
            return cursor.rowcount > 0

    # ---------------------------------------------------------
    # DUPLICATE GROUPS
    # ---------------------------------------------------------

    def get_or_create_group(
        self, fingerprint: str, method: str, threshold: Optional[float] = None
    ) -> dict[str, Any]:
        with get_db_connection(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM notification_groups WHERE fingerprint = ? AND grouping_method = ?",
                (fingerprint, method),
            )
            row = cursor.fetchone()
            if row:
                return dict(row)

            group_id = str(uuid.uuid4())
            now_iso = datetime.now(timezone.utc).isoformat()
            cursor.execute(
                """
                INSERT INTO notification_groups (id, fingerprint, grouping_method, similarity_threshold, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (group_id, fingerprint, method, threshold, now_iso),
            )
            conn.commit()
            return {
                "id": group_id,
                "fingerprint": fingerprint,
                "grouping_method": method,
                "similarity_threshold": threshold,
                "created_at": now_iso,
            }

    def list_duplicate_groups(self) -> list[dict[str, Any]]:
        with get_db_connection(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT g.*, COUNT(n.id) as group_size,
                       MIN(n.received_at) as earliest_event,
                       MAX(n.received_at) as latest_event,
                       MIN(n.title) as sample_title
                FROM notification_groups g
                JOIN notifications n ON n.duplicate_group_id = g.id
                GROUP BY g.id
                HAVING COUNT(n.id) > 1
                ORDER BY group_size DESC
                """
            )
            return [dict(row) for row in cursor.fetchall()]

    def get_group_members(self, group_id: str) -> list[dict[str, Any]]:
        with get_db_connection(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM notifications WHERE duplicate_group_id = ? ORDER BY received_at ASC",
                (group_id,),
            )
            return [dict(row) for row in cursor.fetchall()]

    # ---------------------------------------------------------
    # FEEDBACK
    # ---------------------------------------------------------

    def record_feedback(
        self,
        notification_id: str,
        feedback_type: str,
        original_value: str,
        corrected_value: str,
    ) -> dict[str, Any]:
        feedback_id = str(uuid.uuid4())
        now_iso = datetime.now(timezone.utc).isoformat()
        with get_db_connection(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO feedback (id, notification_id, feedback_type, original_value, corrected_value, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (feedback_id, notification_id, feedback_type, original_value, corrected_value, now_iso),
            )

            # Apply correction to notification directly if applicable
            if feedback_type == "category":
                cursor.execute(
                    "UPDATE notifications SET category = ? WHERE id = ?",
                    (corrected_value, notification_id),
                )
            elif feedback_type == "priority_level":
                cursor.execute(
                    "UPDATE notifications SET priority_level = ? WHERE id = ?",
                    (corrected_value, notification_id),
                )

            conn.commit()

        return {
            "id": feedback_id,
            "notification_id": notification_id,
            "feedback_type": feedback_type,
            "original_value": original_value,
            "corrected_value": corrected_value,
            "created_at": now_iso,
        }

    def list_feedback(self, limit: int = 100) -> list[dict[str, Any]]:
        with get_db_connection(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT f.*, n.title as notification_title, n.package_name
                FROM feedback f
                LEFT JOIN notifications n ON f.notification_id = n.id
                ORDER BY f.created_at DESC LIMIT ?
                """,
                (limit,),
            )
            return [dict(row) for row in cursor.fetchall()]

    # ---------------------------------------------------------
    # SETTINGS
    # ---------------------------------------------------------

    def get_setting(self, key: str, default: Optional[str] = None) -> Optional[str]:
        with get_db_connection(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT value FROM settings WHERE key = ?", (key,))
            row = cursor.fetchone()
            return row["value"] if row else default

    def set_setting(self, key: str, value: str) -> None:
        now_iso = datetime.now(timezone.utc).isoformat()
        with get_db_connection(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO settings (key, value, updated_at) VALUES (?, ?, ?)
                ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at
                """,
                (key, value, now_iso),
            )
            conn.commit()

    def get_all_settings(self) -> dict[str, str]:
        with get_db_connection(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT key, value FROM settings")
            return {row["key"]: row["value"] for row in cursor.fetchall()}

    # ---------------------------------------------------------
    # ANALYTICS & AGGREGATIONS
    # ---------------------------------------------------------

    def get_analytics_summary(self) -> dict[str, Any]:
        with get_db_connection(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM notifications")
            total_notifications = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM notifications WHERE priority_level = 'high'")
            high_priority = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM notifications WHERE action_detected = 1")
            action_required = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM notifications WHERE deadline_status = 'resolved'")
            upcoming_deadlines = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM notifications WHERE is_duplicate = 1")
            duplicate_count = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM notifications WHERE category = 'promotional'")
            promotional_count = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM notifications WHERE category_confidence < 0.60")
            needs_review_count = cursor.fetchone()[0]

            return {
                "total_notifications": total_notifications,
                "high_priority": high_priority,
                "action_required": action_required,
                "upcoming_deadlines": upcoming_deadlines,
                "duplicate_count": duplicate_count,
                "promotional_count": promotional_count,
                "needs_review_count": needs_review_count,
            }

    def get_category_counts(self) -> list[dict[str, Any]]:
        with get_db_connection(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT category, COUNT(*) as count, AVG(category_confidence) as avg_confidence
                FROM notifications
                GROUP BY category
                ORDER BY count DESC
                """
            )
            return [dict(row) for row in cursor.fetchall()]

    def get_priority_counts(self) -> list[dict[str, Any]]:
        with get_db_connection(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT priority_level, COUNT(*) as count, AVG(priority_score) as avg_score
                FROM notifications
                GROUP BY priority_level
                ORDER BY CASE priority_level
                    WHEN 'high' THEN 1
                    WHEN 'medium' THEN 2
                    WHEN 'low' THEN 3
                    ELSE 4
                END
                """
            )
            return [dict(row) for row in cursor.fetchall()]

    def get_timeline_volume(self) -> list[dict[str, Any]]:
        with get_db_connection(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT substr(received_at, 1, 13) as hour_bucket, COUNT(*) as count
                FROM notifications
                GROUP BY hour_bucket
                ORDER BY hour_bucket ASC
                """
            )
            return [dict(row) for row in cursor.fetchall()]

    def get_app_distribution(self) -> list[dict[str, Any]]:
        with get_db_connection(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT package_name, COUNT(*) as count,
                       SUM(CASE WHEN priority_level = 'high' THEN 1 ELSE 0 END) as high_count
                FROM notifications
                GROUP BY package_name
                ORDER BY count DESC
                LIMIT 15
                """
            )
            return [dict(row) for row in cursor.fetchall()]

    def get_notification_stats_by_app(self) -> list[dict[str, Any]]:
        with get_db_connection(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT 
                    package_name,
                    COUNT(*) as total_notifications,
                    COUNT(*) as count,
                    SUM(CASE WHEN priority_level = 'high' THEN 1 ELSE 0 END) as high_priority_count,
                    SUM(CASE WHEN priority_level = 'high' THEN 1 ELSE 0 END) as high_count,
                    SUM(CASE WHEN priority_level = 'medium' THEN 1 ELSE 0 END) as medium_priority_count,
                    SUM(CASE WHEN priority_level = 'low' THEN 1 ELSE 0 END) as low_priority_count,
                    SUM(CASE WHEN action_detected = 1 THEN 1 ELSE 0 END) as action_count,
                    SUM(CASE WHEN deadline_status IN ('resolved', 'unresolved') THEN 1 ELSE 0 END) as deadline_count,
                    SUM(CASE WHEN is_read = 0 THEN 1 ELSE 0 END) as unread_count,
                    ROUND(AVG(priority_score), 2) as avg_priority_score,
                    MAX(received_at) as latest_notification_at
                FROM notifications
                GROUP BY package_name
                ORDER BY total_notifications DESC
                """
            )
            return [dict(row) for row in cursor.fetchall()]

    def get_overdue_deadlines(self, reference_time_iso: Optional[str] = None) -> list[dict[str, Any]]:
        ref_time = reference_time_iso or datetime.now(timezone.utc).isoformat()
        with get_db_connection(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT * FROM notifications
                WHERE deadline_at IS NOT NULL
                  AND deadline_at != ''
                  AND deadline_at < ?
                ORDER BY deadline_at ASC
                """,
                (ref_time,),
            )
            rows = cursor.fetchall()
            results = []
            for row in rows:
                item = dict(row)
                item["priority_reasons"] = json.loads(item.get("priority_reasons") or "[]")
                item["action_detected"] = bool(item.get("action_detected"))
                item["is_duplicate"] = bool(item.get("is_duplicate"))
                item["is_read"] = bool(item.get("is_read"))
                results.append(item)
            return results

    def get_unread_high_priority(self, limit: int = 50) -> list[dict[str, Any]]:
        with get_db_connection(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT * FROM notifications
                WHERE is_read = 0 AND priority_level = 'high'
                ORDER BY priority_score DESC, received_at DESC
                LIMIT ?
                """,
                (limit,),
            )
            rows = cursor.fetchall()
            results = []
            for row in rows:
                item = dict(row)
                item["priority_reasons"] = json.loads(item.get("priority_reasons") or "[]")
                item["action_detected"] = bool(item.get("action_detected"))
                item["is_duplicate"] = bool(item.get("is_duplicate"))
                item["is_read"] = bool(item.get("is_read"))
                results.append(item)
            return results

    def get_low_confidence_notifications(
        self, threshold: float = 0.60, limit: int = 50
    ) -> list[dict[str, Any]]:
        with get_db_connection(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT * FROM notifications
                WHERE category_confidence < ?
                ORDER BY category_confidence ASC, received_at DESC
                LIMIT ?
                """,
                (threshold, limit),
            )
            rows = cursor.fetchall()
            results = []
            for row in rows:
                item = dict(row)
                item["priority_reasons"] = json.loads(item.get("priority_reasons") or "[]")
                item["action_detected"] = bool(item.get("action_detected"))
                item["is_duplicate"] = bool(item.get("is_duplicate"))
                item["is_read"] = bool(item.get("is_read"))
                results.append(item)
            return results

    # ---------------------------------------------------------
    # PRIVACY & PURGE
    # ---------------------------------------------------------

    def purge_all_data(self) -> dict[str, int]:
        """Safely wipes all captured notification data, actions, groups, and feedback."""
        with get_db_connection(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM feedback")
            deleted_feedback = cursor.rowcount
            cursor.execute("DELETE FROM actions")
            deleted_actions = cursor.rowcount
            cursor.execute("DELETE FROM notifications")
            deleted_notifications = cursor.rowcount
            cursor.execute("DELETE FROM notification_groups")
            deleted_groups = cursor.rowcount
            conn.commit()

            return {
                "deleted_notifications": deleted_notifications,
                "deleted_actions": deleted_actions,
                "deleted_feedback": deleted_feedback,
                "deleted_groups": deleted_groups,
            }

    def cleanup_expired_retention(self) -> int:
        now_iso = datetime.now(timezone.utc).isoformat()
        with get_db_connection(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "DELETE FROM notifications WHERE retention_expires_at IS NOT NULL AND retention_expires_at <= ?",
                (now_iso,),
            )
            conn.commit()
            return cursor.rowcount
