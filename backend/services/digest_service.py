"""
AI Daily Digest & Executive Briefing Service for NotifyIQ.
Synthesizes notification stream metadata, high-priority actions, deadlines,
shopping deals, and noise reduction into a concise daily briefing.
"""

from datetime import datetime, date, timezone
from typing import Any, Optional
from pydantic import BaseModel, Field
from backend.database.repository import Repository


class DailyDigest(BaseModel):
    date: str
    headline: str
    narrative: str
    total_received: int
    high_priority_count: int
    actions_due_today: list[dict[str, Any]]
    top_deals: list[dict[str, Any]]
    duplicates_filtered: int
    cognitive_overload_level: str  # "low", "moderate", "high"
    cognitive_overload_score: float  # 0.0 to 100.0


class DigestService:
    def __init__(self, repository: Optional[Repository] = None):
        self.repo = repository or Repository()

    def generate_daily_digest(self, target_date: Optional[date] = None) -> DailyDigest:
        """
        Synthesizes notification stream and actions into an executive briefing.
        Runs completely locally offline without cloud LLM dependencies.
        """
        now = datetime.now(timezone.utc)
        eval_date = target_date or now.date()
        date_str = eval_date.isoformat()

        # Fetch notifications and actions
        all_notifications, total_count = self.repo.list_notifications(limit=500)
        open_actions = self.repo.list_actions(status="open", limit=100)
        summary = self.repo.get_analytics_summary()

        # Filter items for target date or upcoming
        high_prio_items = [n for n in all_notifications if n.get("priority_level") == "high"]
        
        # Actions due today / upcoming
        actions_due = []
        for a in open_actions:
            dl = a.get("deadline_at")
            if dl:
                actions_due.append({
                    "id": a.get("id"),
                    "action_text": a.get("action_text"),
                    "package_name": a.get("package_name"),
                    "deadline_at": dl,
                })

        # Check shopping price drops / deals
        price_alerts_raw = self.repo.get_setting("user_price_alerts") or "[]"
        import json
        try:
            stored_alerts = json.loads(price_alerts_raw)
        except Exception:
            stored_alerts = []

        top_deals = []
        for alert in stored_alerts[-3:]:
            top_deals.append({
                "product_title": alert.get("product_title", "")[:35],
                "target_price": alert.get("target_price"),
                "current_price": alert.get("current_price"),
            })

        duplicates_count = summary.get("duplicate_count", 0)

        # Calculate Cognitive Overload Score (0 to 100)
        # Factors: total notification volume (weight 0.4), high priority volume (weight 0.4), pending actions (weight 0.2)
        vol_score = min(100.0, (total_count / 50.0) * 100.0)
        prio_score = min(100.0, (len(high_prio_items) / 5.0) * 100.0)
        action_score = min(100.0, (len(actions_due) / 5.0) * 100.0)
        overload_score = round(0.4 * vol_score + 0.4 * prio_score + 0.2 * action_score, 1)

        if overload_score > 65.0:
            overload_level = "high"
        elif overload_score > 35.0:
            overload_level = "moderate"
        else:
            overload_level = "low"

        # Construct concise executive narrative
        narrative_parts = []
        if total_count == 0:
            headline = "Quiet Day — Zero Alerts"
            narrative = "No notifications have been recorded yet. Your inbox is clean and calm."
        else:
            if len(actions_due) > 0 and len(high_prio_items) > 0:
                headline = f"Action Required: {len(actions_due)} pending tasks detected"
                narrative_parts.append(
                    f"You have **{total_count} total notifications** in your stream, with **{len(high_prio_items)} marked high priority**."
                )
                narrative_parts.append(
                    f"There are **{len(actions_due)} actionable deadlines** requiring your attention (including *{actions_due[0]['action_text']}*)."
                )
            elif len(high_prio_items) > 0:
                headline = f"Notice: {len(high_prio_items)} high-priority updates"
                narrative_parts.append(
                    f"Your notification stream contains **{total_count} alerts** with **{len(high_prio_items)} urgent messages**."
                )
            else:
                headline = "Notification Stream Calm"
                narrative_parts.append(
                    f"Processed **{total_count} notifications**. Most messages are low-priority informational or social updates."
                )

            if duplicates_count > 0:
                narrative_parts.append(
                    f"NotifyIQ grouped **{duplicates_count} repeated alerts** to preserve your focus."
                )

            if len(top_deals) > 0:
                narrative_parts.append(
                    f"Tracking **{len(top_deals)} shopping items** for active price drops."
                )

            narrative = " ".join(narrative_parts)

        return DailyDigest(
            date=date_str,
            headline=headline,
            narrative=narrative,
            total_received=total_count,
            high_priority_count=len(high_prio_items),
            actions_due_today=actions_due[:5],
            top_deals=top_deals,
            duplicates_filtered=duplicates_count,
            cognitive_overload_level=overload_level,
            cognitive_overload_score=overload_score,
        )
